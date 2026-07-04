#!/usr/bin/env python3
"""Reconcile already-bound Q315 content against the existing language pages.

``prepare_missing_content.py`` inventories *unbound* text and proposes new
items. This tool is its complement: it looks only at slots that are already
bound to a QID and asks whether the bound item's stored multilingual value
still matches what the corresponding rendered language page actually shows.

The round-trip verifier reports *that* a binding does not reproduce a page; it
does not say what the page has instead, and it cannot tell a genuinely wrong
translation apart from a language page that never had the slot at all. This
tool aligns each binding to its slot in every language page and classifies the
difference so corrections can be prepared safely:

``match``
    stored value equals the page value; nothing to do.
``differs``
    the page renders a *different* non-empty value. The rendered page is the
    migration authority, so a reviewed correction is proposed that aligns the
    Wikibase item to the page.
``wikibase-missing``
    the page has a value but the item has none for that language; a reviewed
    addition is proposed from page evidence.
``page-absent``
    the language page does not contain the slot at all. This is legacy-page
    incompleteness, **not** a Wikibase error. No statement is emitted: blindly
    overwriting a good translation with nothing would destroy content. These
    rows are reported as a page-completeness backlog only.

Like every other generator here, the QuickStatements it writes are review
material, not an authority. Nothing is imported and no HTML is changed.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import alternate_pages, page_sources
from abstract.prepare_travel_content import (
    LANGUAGES,
    exported_text,
    quote,
    slots,
)
from abstract.verify_content_roundtrip import COMPOSED_RESULT_ITEMTYPES, labels

DEFAULT_DATA = DEFAULT_REPO_ROOT.parent / "Q42761025" / "data"
DEFAULT_REVIEW = HERE / "content-corrections-review.csv"
DEFAULT_QUICKSTATEMENTS = HERE / "content-corrections.quickstatements"

CONTENT_ITEMTYPE = "Q3185"
MONOLINGUAL_CONTENT_PROPERTY = "P40"


class BoundSlots(HTMLParser):
    """Map each bound slot to ``(kind, qid)`` using the ``slots`` key scheme.

    The slot key ``(tag, class, role, occurrence)`` is computed exactly as
    :class:`~abstract.prepare_travel_content.DirectTextSlots` computes it, so a
    key found here indexes the same slot in a rendered language page. Bindings
    nested inside a ``q-call`` are ignored, matching the round-trip verifier:
    their value is a composed result, not a stored label.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.bindings: dict[tuple[str, str, str, int], tuple[str, str]] = {}
        self.call_depth = 0

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        base = (
            tag,
            ".".join(sorted((values.get("class") or "").split())),
            values.get("role") or "",
        )
        key = (*base, self.counts[base])
        self.counts[base] += 1
        if tag == "q-call":
            self.call_depth += 1
            return
        if self.call_depth:
            return
        for kind in ("data-content", "data-entity"):
            value = values.get(kind) or ""
            if value.startswith("local:"):
                self.bindings[key] = (kind, value.removeprefix("local:"))

    def handle_endtag(self, tag) -> None:
        if tag == "q-call" and self.call_depth:
            self.call_depth -= 1


def bound_slots(path: Path) -> dict[tuple[str, str, str, int], tuple[str, str]]:
    parser = BoundSlots()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.bindings


def page_degraded(page_value: str, stored: str) -> bool:
    """Return whether the page value is a corrupted rendering of ``stored``.

    Some legacy pages carry the Unicode replacement character or plain ``?``
    where an accented letter belonged. Wikibase holds the intact text, so such
    a difference must never drive a "correction" that overwrites good data with
    the damaged page string. A value is treated as degraded when it contains a
    replacement character, or when it equals ``stored`` with every non-ASCII
    character flattened to ``?`` (the exact signature of a lossy re-encoding).
    """
    if "�" in page_value:
        return True
    if "?" in page_value and "?" not in stored:
        flattened = re.sub(r"[^\x00-\x7f]", "?", stored)
        return page_value == flattened
    return False


def normalize(value: str) -> str:
    """Collapse differences that are not real content differences.

    Zero-width joiners and non-joiners and non-breaking spaces vary freely
    between a stored label and a rendered page without changing the reading;
    treating them as differences would produce pure churn.
    """
    return (
        value.replace("‌", "")
        .replace("‍", "")
        .replace(" ", " ")
        .strip()
    )


def _fold(value: str) -> str:
    """Reduce a string to its case-, accent- and punctuation-free skeleton."""
    decomposed = unicodedata.normalize("NFKD", value)
    letters = [
        character
        for character in decomposed
        if not unicodedata.combining(character) and character.isalnum()
    ]
    return "".join(letters).casefold()


def typographic_variant(page_value: str, stored: str) -> bool:
    """Return whether the two strings are the same content up to typography.

    A correctly aligned slot whose translation needs fixing differs from the
    stored value only in case, accent, spacing or punctuation, so its skeleton
    is unchanged. Occurrence drift, by contrast, aligns a binding to an
    entirely different element and produces a different skeleton. Restricting
    automatic corrections to skeleton-equal differences keeps a misaligned slot
    from overwriting a good value with an unrelated one.
    """
    skeleton = _fold(page_value)
    return bool(skeleton) and skeleton == _fold(stored) and page_value != stored


def classify(
    repo_root: Path,
    data_dir: Path,
    sources: list[tuple[str, Path]],
) -> list[dict[str, str]]:
    label_rows = labels(data_dir)
    rows: list[dict[str, str]] = []
    for page_qid, relative in sources:
        abstract = (repo_root / relative).resolve()
        targets = alternate_pages(repo_root, abstract)
        localized = {
            language: slots(target)
            for language, target in zip(LANGUAGES, targets)
        }
        for key, (kind, qid) in bound_slots(abstract).items():
            row = label_rows.get(qid, {})
            itemtype = row.get("itemtype", "").strip()
            if itemtype in COMPOSED_RESULT_ITEMTYPES:
                continue
            tag, class_name, role, occurrence = key
            # Occurrence-based slot keys can drift between structurally
            # divergent language pages, binding one QID to different elements.
            # A correction is only trustworthy when English confirms the
            # alignment: the item's stored English equals the English page
            # value at this exact slot. Otherwise every language of this slot
            # is reported for review but drives no automated statement.
            stored_en = exported_text(row.get("en") or "")
            english_page = (localized["en"].get(key) or "").strip()
            aligned = bool(stored_en) and normalize(english_page) == normalize(stored_en)
            for language in LANGUAGES:
                stored = exported_text(row.get(language) or "")
                page_value = (localized[language].get(key) or "").strip()
                if not page_value:
                    status = "page-absent"
                elif not stored:
                    status = "wikibase-missing"
                elif normalize(stored) == normalize(page_value):
                    status = "match"
                elif page_degraded(page_value, stored):
                    status = "page-degraded"
                else:
                    status = "differs"
                rows.append(
                    {
                        "page": page_qid,
                        "path": relative.as_posix(),
                        "qid": qid,
                        "kind": kind,
                        "itemtype": itemtype,
                        "tag": tag,
                        "class": class_name,
                        "role": role,
                        "occurrence": str(occurrence),
                        "language": language,
                        "status": status,
                        "aligned": "yes" if aligned else "",
                        "stored_value": stored,
                        "page_value": page_value,
                        "looks_untranslated": (
                            "yes"
                            if status in {"differs", "wikibase-missing"}
                            and language != "en"
                            and page_value
                            and page_value == english_page
                            else ""
                        ),
                    }
                )
    return rows


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    fields = (
        "page", "path", "qid", "kind", "itemtype", "tag", "class", "role",
        "occurrence", "language", "status", "aligned", "looks_untranslated",
        "stored_value", "page_value",
    )
    reportable = [row for row in rows if row["status"] != "match"]
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reportable)


def write_quickstatements(path: Path, rows: list[dict[str, str]]) -> int:
    """Emit one reviewed edit block per item that needs alignment to a page.

    Only ``differs`` and ``wikibase-missing`` produce statements, and only
    where the page supplies a value. ``page-absent`` never does: a language
    page that lacks the slot is a page-completeness problem, and emitting a
    removal would delete a translation the item legitimately holds.
    """
    by_item: dict[str, list[str]] = {}
    corrected: set[str] = set()
    for row in rows:
        if row["status"] not in {"differs", "wikibase-missing"}:
            continue
        if not row["page_value"]:
            continue
        # Only English-confirmed slots, and never English itself: an English
        # difference has no independent anchor, so it stays review-only.
        if row["aligned"] != "yes" or row["language"] == "en":
            continue
        # A ``differs`` slot is only corrected when the page value is the same
        # content up to typography; a wholly different string is occurrence
        # drift, not a translation fix, and is left to human review. A
        # ``wikibase-missing`` addition is refused when the page merely repeats
        # the English text: that is an untranslated page, not a translation.
        if row["status"] == "differs" and not typographic_variant(
            row["page_value"], row["stored_value"]
        ):
            continue
        if row["status"] == "wikibase-missing" and row["looks_untranslated"] == "yes":
            continue
        qid = row["qid"]
        language = row["language"]
        statements = by_item.setdefault(qid, [])
        is_content = row["itemtype"] in {"", CONTENT_ITEMTYPE}
        # A monolingual content value is single-valued per language: remove the
        # stale value before adding the corrected one so the item is not left
        # holding both. Labels are single-valued and simply overwrite.
        if row["status"] == "differs" and is_content and row["stored_value"]:
            statements.append(
                f'-{qid}|{MONOLINGUAL_CONTENT_PROPERTY}|'
                f'{language}:"{quote(row["stored_value"])}"'
            )
        statements.append(f'{qid}|L{language}|"{quote(row["page_value"])}"')
        if is_content:
            statements.append(
                f'{qid}|{MONOLINGUAL_CONTENT_PROPERTY}|'
                f'{language}:"{quote(row["page_value"])}"'
            )
        corrected.add(qid)
    blocks = ["\n".join(by_item[qid]) for qid in sorted(corrected)]
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return len(corrected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--page",
        default="",
        help="restrict the reconciliation to a single abstract page QID",
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument(
        "--quickstatements", type=Path, default=DEFAULT_QUICKSTATEMENTS
    )
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        sources = page_sources(repo_root, args.page)
        rows = classify(repo_root, args.data_dir.resolve(), sources)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    write_review(args.review, rows)
    corrected = write_quickstatements(args.quickstatements, rows)
    counts: Counter[str] = Counter(row["status"] for row in rows)
    print(
        f"Reconciled {len(rows)} bound slot/language pairs; "
        f"{corrected} item(s) have reviewed corrections ready"
    )
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
