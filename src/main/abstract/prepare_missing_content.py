#!/usr/bin/env python3
"""Inventory abstract-page text and prepare safe local Wikibase imports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import defaultdict
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import abstract_sources
from abstract.prepare_travel_content import (
    LANGUAGES,
    QID_TEXT,
    content_bindings,
    existing_content,
    local_id,
    quote,
    slots,
)

DEFAULT_REVIEW = HERE / "missing-content-review.csv"
DEFAULT_QUICKSTATEMENTS = HERE / "missing-content.quickstatements"
DEFAULT_PARTIAL_QUICKSTATEMENTS = HERE / "missing-content-partial.quickstatements"
DEFAULT_TRANSLATIONS = HERE / "missing-content-translations.csv"
DEFAULT_LABEL_UPDATES = HERE / "missing-content-label-updates.quickstatements"

# Abstract pages whose content is a curated list of proper names — film, book,
# series and museum titles, and verbatim quotes. These titles must never be
# translated: the English page already carries the correct native-language
# label for every entry (a Malayalam film keeps its Malayalam title on the
# English page), so every language reuses that authoritative English value
# verbatim and no P40 translation is emitted. Identified by their English
# source path so the rule survives QID renumbering.
NATIVE_LABEL_SOURCES = frozenset(
    {
        "en/writings/books-i-read.html",
        "en/writings/films-series-documentaries.html",
        "en/writings/music.html",
        "en/writings/museums-galleries.html",
        "en/writings/quotes.html",
    }
)


class Alternates(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: dict[str, str] = {}

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "alternate":
            language = values.get("hreflang")
            href = values.get("href")
            if language in LANGUAGES and href:
                self.links[language] = href


class SlotMetadata(HTMLParser):
    """Collect attributes using the same signatures as DirectTextSlots."""

    def __init__(self) -> None:
        super().__init__()
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.attributes: dict[tuple[str, str, str, int], dict[str, str | None]] = {}

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        base = (
            tag,
            ".".join(sorted((values.get("class") or "").split())),
            values.get("role") or "",
        )
        occurrence = self.counts[base]
        self.counts[base] += 1
        self.attributes[(*base, occurrence)] = values


def slot_metadata(path: Path) -> dict[tuple[str, str, str, int], dict[str, str | None]]:
    parser = SlotMetadata()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.attributes


def alternate_pages(repo_root: Path, abstract_page: Path) -> list[Path]:
    parser = Alternates()
    parser.feed(abstract_page.read_text(encoding="utf-8"))
    missing = [language for language in LANGUAGES if language not in parser.links]
    if missing:
        raise ValueError(
            f"{abstract_page}: missing hreflang alternates: {', '.join(missing)}"
        )
    pages = []
    for language in LANGUAGES:
        href = unquote(urlparse(parser.links[language]).path)
        page = (abstract_page.parent / href).resolve()
        try:
            page.relative_to(repo_root)
        except ValueError as error:
            raise ValueError(f"{abstract_page}: alternate escapes repository: {href}") from error
        if not page.is_file():
            raise ValueError(f"{abstract_page}: alternate does not exist: {page}")
        pages.append(page)
    return pages


def page_sources(repo_root: Path, page: str = "") -> list[tuple[str, Path]]:
    """Return the abstract pages to inventory, discovered from the repository.

    This is the generic replacement for the former committed page-list CSV: the
    abstract pages are derived from ``data-abstract-page`` declarations, so any
    newly authored page is covered without editing a hand-written list.
    """
    return abstract_sources(repo_root, page)


def english_index(data_dir: Path) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for name in ("abstract-content-items.csv", "labels-wikibase.csv"):
        path = data_dir / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if (
                    name == "labels-wikibase.csv"
                    and row.get("itemtype")
                    and row["itemtype"].strip() != "Q3185"
                ):
                    continue
                qid = local_id(row.get("item") or row.get("identifier") or "")
                english = (row.get("en") or "").strip()
                if re.fullmatch(r"Q[0-9]+", qid) and english:
                    index[english.casefold()].add(qid)
    return index


def content_values_by_qid(data_dir: Path) -> dict[str, tuple[str, ...]]:
    """Return exported multilingual values for candidate disambiguation."""
    result: dict[str, tuple[str, ...]] = {}
    path = data_dir / "labels-wikibase.csv"
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = (row.get("identifier") or "").strip()
            if (
                re.fullmatch(r"Q[1-9][0-9]*", qid)
                and (row.get("itemtype") or "").strip() == "Q3185"
            ):
                result[qid] = tuple(
                    (row.get(language) or "").strip() for language in LANGUAGES
                )
    return result


def best_candidate(
    candidates: list[str],
    values: tuple[str, ...],
    exported: dict[str, tuple[str, ...]],
) -> str:
    """Choose a unique candidate corroborated by multiple language values."""
    scores = {}
    for qid in candidates:
        candidate = exported.get(qid, ())
        scores[qid] = sum(
            bool(value)
            and bool(candidate_value)
            and value.casefold() == candidate_value.casefold()
            for value, candidate_value in zip(values, candidate)
        )
    if not scores:
        return ""
    highest = max(scores.values())
    winners = [qid for qid, score in scores.items() if score == highest]
    if highest >= 2 and len(winners) == 1:
        return winners[0]
    # When legacy page order makes every non-English occurrence unusable,
    # prefer the uniquely complete multilingual item among candidates that
    # share the same English value.
    if highest == 1 and len(winners) > 1:
        completeness = {
            qid: sum(bool(value) for value in exported.get(qid, ()))
            for qid in winners
        }
        most_complete = max(completeness.values())
        complete_winners = [
            qid for qid, count in completeness.items() if count == most_complete
        ]
        if most_complete > 1 and len(complete_winners) == 1:
            return complete_winners[0]
    return ""


def import_token_index(data_dir: Path) -> dict[str, str]:
    path = data_dir / "labels-wikibase.csv"
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = (row.get("identifier") or "").strip()
            label = (row.get("en") or "").strip()
            match = re.fullmatch(r"(M[A-F0-9]{12}) abstract content", label)
            if match and re.fullmatch(r"Q[1-9][0-9]*", qid):
                token = match.group(1)
                previous = result.get(token)
                if previous and previous != qid:
                    raise ValueError(
                        f"{path}: import token {token} maps to {previous} and {qid}"
                    )
                result[token] = qid
    return result


def content_token(values: tuple[str, ...]) -> str:
    """Return a stable import token independent of inventory ordering."""
    payload = "\x1f".join(value.strip() for value in values).encode("utf-8")
    return "M" + hashlib.sha256(payload).hexdigest()[:12].upper()


def load_translations(path: Path) -> dict[str, dict[str, str]]:
    """Read reviewed translations keyed by stable content token and language."""
    result: dict[str, dict[str, str]] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            token = (row.get("token") or "").strip()
            language = (row.get("language") or "").strip()
            text = (row.get("text") or "").strip()
            if (
                re.fullmatch(r"M[A-F0-9]{12}", token)
                and language in LANGUAGES
                and text
            ):
                result.setdefault(token, {})[language] = text
    return result


def fill_translations(
    values: tuple[str, ...], translations: dict[str, str]
) -> tuple[str, ...]:
    """Fill absent values without overwriting text supplied by a language page."""
    return tuple(
        value if value else translations.get(language, "")
        for language, value in zip(LANGUAGES, values)
    )


def inventory(
    repo_root: Path,
    data_dir: Path,
    sources: list[tuple[str, Path]],
    translations: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    translations = translations or {}
    exact = existing_content(data_dir)
    by_english = english_index(data_dir)
    by_qid = content_values_by_qid(data_dir)
    by_token = import_token_index(data_dir)
    rows: list[dict[str, str]] = []
    missing_tokens: dict[tuple[str, ...], str] = {}
    for page_id, relative in sources:
        abstract_page = (repo_root / relative).resolve()
        localized_pages = alternate_pages(repo_root, abstract_page)
        # LANGUAGES[0] is English, so the first alternate is the English source
        # page whose labels are authoritative for native-label list pages.
        english_source = localized_pages[0].relative_to(repo_root).as_posix()
        native_labels = english_source in NATIVE_LABEL_SOURCES
        localized = [slots(page) for page in localized_pages]
        signature_counts = [
            Counter(key[:3] for key in page) for page in localized
        ]
        bindings = content_bindings(abstract_page)
        metadata = slot_metadata(abstract_page)
        for key, abstract_text in slots(abstract_page).items():
            if key in bindings or QID_TEXT.fullmatch(abstract_text):
                continue
            attributes = metadata.get(key, {})
            # Language-switcher names identify the linked document language;
            # they are metadata/interface literals, not article content.
            if attributes.get("property") == "inLanguage":
                continue
            href = attributes.get("href") or ""
            # External service names are proper names, not translatable content
            # components. Keeping them literal also prevents structurally older
            # localized footers from shifting occurrence-based alignment.
            if key[0] == "a" and urlparse(href).scheme in {"http", "https"}:
                continue
            if not any(character.isalnum() for character in abstract_text):
                continue
            english_count = signature_counts[0].get(key[:3], 0)
            english_aligned = (
                localized[0].get(key, "").strip() == abstract_text.strip()
            )
            legacy_values = (
                tuple(
                    page.get(key, "")
                    if signature_counts[index].get(key[:3], 0) == english_count
                    else ""
                    for index, page in enumerate(localized)
                )
                if english_aligned
                else ("",) * len(LANGUAGES)
            )
            # The canonical unbound text is the migration source when a legacy
            # English page has a structurally divergent repeated element list.
            # This makes the slot reviewable without aligning it to unrelated
            # occurrence N on that page.
            # Canonical Q315 is authoritative for the source-language value.
            # A legacy English page can have the same repeated-element count
            # yet a different order, so occurrence N is not sufficient proof
            # that its text belongs to this canonical slot.
            legacy_values = (abstract_text, *legacy_values[1:])
            legacy_token = content_token(legacy_values)
            source_values = (abstract_text, *("" for _ in LANGUAGES[1:]))
            token = content_token(source_values)
            values = fill_translations(source_values, translations.get(token, {}))
            if native_labels:
                # Proper-name list pages (film/book/series/museum titles,
                # quotes) carry the authoritative label on the English page.
                # Every language reuses that value verbatim instead of a
                # translation, so downstream P40 content and labels stay native.
                values = (values[0],) * len(LANGUAGES)
            candidates = sorted(by_english.get(values[0].casefold(), set())) if values[0] else []
            qid = exact.get(values, "")
            # Link destination identity and visible link text are independent.
            # "Read more about me" must not resolve to the destination page's
            # shorter "About" label merely because its href contains that QID.
            if token in by_token:
                status = "existing-import-token"
                qid = by_token[token]
            elif legacy_token in by_token:
                # Reconcile items imported before canonical-English-only
                # alignment replaced unsafe occurrence-paired translations.
                status = "existing-import-token"
                qid = by_token[legacy_token]
            elif qid:
                status = "existing-exact"
            elif len(candidates) == 1:
                status = "existing-english-review"
                qid = candidates[0]
            elif candidates:
                corroborated = best_candidate(candidates, values, by_qid)
                if corroborated:
                    status = "existing-english-review"
                    qid = corroborated
                else:
                    status = "ambiguous-review"
            elif all(values):
                status = "missing-ready"
            else:
                status = "missing-translations"
            tag, class_name, role, occurrence = key
            row = {
                "page": page_id,
                "path": relative.as_posix(),
                "native_labels": "1" if native_labels else "",
                "tag": tag,
                "class": class_name,
                "role": role,
                "occurrence": str(occurrence),
                "status": status,
                "qid": qid,
                "candidates": ";".join(candidates),
                "token": (
                    missing_tokens.setdefault(values, token)
                    if status in {
                        "missing-ready",
                        "missing-translations",
                        "existing-import-token",
                    }
                    and token
                    else ""
                ),
                "abstract_text": abstract_text,
            }
            row.update(dict(zip(LANGUAGES, values)))
            rows.append(row)
    return rows


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    fields = (
        "page", "path", "native_labels", "tag", "class", "role", "occurrence",
        "status", "qid", "candidates", "token", "abstract_text", *LANGUAGES,
    )
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_quickstatements(path: Path, rows: list[dict[str, str]]) -> int:
    ready = {
        row["token"]: row for row in rows if row["status"] == "missing-ready"
    }
    blocks = []
    for token, row in ready.items():
        statements = ["CREATE", f'LAST|Len|"{token} abstract content"']
        statements.extend(
            f'LAST|P40|{language}:"{quote(row[language])}"'
            for language in LANGUAGES
        )
        statements.extend(
            (
                'LAST|Den|"language-independent content component used by an abstract page"',
                "LAST|P8|Q3185",
            )
        )
        blocks.append("\n".join(statements))
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return len(ready)


def write_label_updates(
    path: Path,
    rows: list[dict[str, str]],
    exported: dict[str, tuple[str, ...]] | None = None,
) -> int:
    """Finalize labels and repair legacy occurrence-paired content values."""
    exported = exported or {}
    imported = {
        row["qid"]: row
        for row in rows
        if row["status"] == "existing-import-token"
        and row["token"]
        and row["qid"]
    }
    blocks = []
    for row in imported.values():
        statements = []
        previous = exported.get(row["qid"], ())
        # Native-label list pages (film/book/series/museum titles, quotes) are
        # proper names that must not be translated: every language reuses the
        # authoritative English value verbatim and no P40 replacement is made,
        # so the untranslated value already imported for each language stays.
        native = bool(row.get("native_labels"))
        for index, language in enumerate(LANGUAGES):
            value = row["en"] if native else row[language]
            if not value:
                continue
            label = value if len(value) <= 250 else value[:247] + "..."
            statements.append(
                f'{row["qid"]}|L{language}|"{quote(label)}"'
            )
            if language != "en" and not native:
                # The initial bulk import used occurrence-aligned legacy values.
                # Replacing P40 makes canonical-English-derived translations
                # authoritative and removes any unrelated value imported from
                # a reordered language page.
                old = previous[index] if index < len(previous) else ""
                if old != value:
                    if old:
                        statements.append(
                            f'-{row["qid"]}|P40|{language}:"{quote(old)}"'
                        )
                    statements.append(
                        f'{row["qid"]}|P40|{language}:"{quote(value)}"'
                    )
        blocks.append("\n".join(statements))
    path.write_text(
        "\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8"
    )
    return len(imported)


def write_partial_quickstatements(path: Path, rows: list[dict[str, str]]) -> int:
    """Write reviewed candidates with en/fr but incomplete target coverage."""
    ready = {
        row["token"]: row
        for row in rows
        if row["status"] == "missing-translations" and row["token"]
    }
    blocks = []
    for token, row in ready.items():
        statements = ["CREATE", f'LAST|Len|"{token} abstract content"']
        statements.extend(
            f'LAST|P40|{language}:"{quote(row[language])}"'
            for language in LANGUAGES
            if row[language]
        )
        statements.extend(
            (
                'LAST|Den|"partially translated language-independent content component"',
                "LAST|P8|Q3185",
            )
        )
        blocks.append("\n".join(statements))
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return len(ready)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_REPO_ROOT.parent / "Q42761025" / "data")
    parser.add_argument(
        "--page",
        default="",
        help="restrict the inventory to a single abstract page QID",
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--quickstatements", type=Path, default=DEFAULT_QUICKSTATEMENTS)
    parser.add_argument(
        "--partial-quickstatements",
        type=Path,
        default=DEFAULT_PARTIAL_QUICKSTATEMENTS,
    )
    parser.add_argument(
        "--translations",
        type=Path,
        default=DEFAULT_TRANSLATIONS,
        help="reviewed token,language,text values that fill absent languages",
    )
    parser.add_argument(
        "--label-updates",
        type=Path,
        default=DEFAULT_LABEL_UPDATES,
        help="post-reconciliation batch replacing temporary token labels",
    )
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        sources = page_sources(repo_root, args.page)
        translations = load_translations(args.translations)
        rows = inventory(
            repo_root, args.data_dir.resolve(), sources, translations
        )
        write_review(args.review, rows)
        ready = write_quickstatements(args.quickstatements, rows)
        partial = write_partial_quickstatements(args.partial_quickstatements, rows)
        label_updates = write_label_updates(
            args.label_updates,
            rows,
            content_values_by_qid(args.data_dir.resolve()),
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["status"]] += 1
    print(
        f"Inventoried {len(rows)} text slots; {ready} complete and "
        f"{partial} partial items ready for review/import; "
        f"{label_updates} imported item labels ready to finalize"
    )
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
