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


def inventory(
    repo_root: Path,
    data_dir: Path,
    sources: list[tuple[str, Path]],
) -> list[dict[str, str]]:
    exact = existing_content(data_dir)
    by_english = english_index(data_dir)
    by_token = import_token_index(data_dir)
    rows: list[dict[str, str]] = []
    missing_tokens: dict[tuple[str, ...], str] = {}
    for page_id, relative in sources:
        abstract_page = (repo_root / relative).resolve()
        localized = [slots(page) for page in alternate_pages(repo_root, abstract_page)]
        bindings = content_bindings(abstract_page)
        metadata = slot_metadata(abstract_page)
        for key, abstract_text in slots(abstract_page).items():
            if key in bindings or QID_TEXT.fullmatch(abstract_text):
                continue
            attributes = metadata.get(key, {})
            href = attributes.get("href") or ""
            # External service names are proper names, not translatable content
            # components. Keeping them literal also prevents structurally older
            # localized footers from shifting occurrence-based alignment.
            if key[0] == "a" and urlparse(href).scheme in {"http", "https"}:
                continue
            if not any(character.isalnum() for character in abstract_text):
                continue
            values = tuple(page.get(key, "") for page in localized)
            candidates = sorted(by_english.get(values[0].casefold(), set())) if values[0] else []
            qid = exact.get(values, "")
            token = content_token(values) if values[0] and values[1] else ""
            # Link destination identity and visible link text are independent.
            # "Read more about me" must not resolve to the destination page's
            # shorter "About" label merely because its href contains that QID.
            if token in by_token:
                status = "existing-import-token"
                qid = by_token[token]
            elif qid:
                status = "existing-exact"
            elif len(candidates) == 1:
                status = "existing-english-review"
                qid = candidates[0]
            elif candidates:
                status = "ambiguous-review"
            elif all(values):
                status = "missing-ready"
            else:
                status = "missing-translations"
            tag, class_name, role, occurrence = key
            row = {
                "page": page_id,
                "path": relative.as_posix(),
                "tag": tag,
                "class": class_name,
                "role": role,
                "occurrence": str(occurrence),
                "status": status,
                "qid": qid,
                "candidates": ";".join(candidates),
                "token": (
                    missing_tokens.setdefault(values, token)
                    if status in {"missing-ready", "missing-translations"}
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
        "page", "path", "tag", "class", "role", "occurrence", "status",
        "qid", "candidates", "token", "abstract_text", *LANGUAGES,
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
        statements = ["CREATE"]
        statements.extend(
            f'LAST|L{language}|"{quote(row[language])}"'
            for language in LANGUAGES
        )
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


def write_partial_quickstatements(path: Path, rows: list[dict[str, str]]) -> int:
    """Write reviewed candidates with en/fr but incomplete target coverage."""
    ready = {
        row["token"]: row
        for row in rows
        if row["status"] == "missing-translations" and row["token"]
    }
    blocks = []
    for token, row in ready.items():
        statements = ["CREATE"]
        statements.extend(
            f'LAST|L{language}|"{quote(row[language])}"'
            for language in LANGUAGES
            if row[language]
        )
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
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        sources = page_sources(repo_root, args.page)
        rows = inventory(repo_root, args.data_dir.resolve(), sources)
        write_review(args.review, rows)
        ready = write_quickstatements(args.quickstatements, rows)
        partial = write_partial_quickstatements(args.partial_quickstatements, rows)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["status"]] += 1
    print(
        f"Inventoried {len(rows)} text slots; {ready} complete and "
        f"{partial} partial items ready for review/import"
    )
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
