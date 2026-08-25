#!/usr/bin/env python3
"""Verify that abstract-page QID bindings reproduce existing language-page text."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import alternate_pages, page_sources
from abstract.prepare_travel_content import LANGUAGES, slots
from abstract.render_page import BINDABLE_ATTRIBUTES, CONTENT_ATTRIBUTE_PREFIX

DEFAULT_DATA = DEFAULT_DATA_DIR
DEFAULT_REPORT = HERE / "content-roundtrip.json"

# A binding whose entity is itself a function-composed result (an abstract
# paragraph) is verified by evaluating its constructor, not by comparing the
# label of the result entity. Identified generically by item type rather than
# by a hard-coded QID.
COMPOSED_RESULT_ITEMTYPES = frozenset({"Q3835"})

# Typographic variants that render identically but differ by code point. A
# content round-trip checks whether the *visible text* is reproducible, so these
# are folded to a single representative on both the label and page-text sides
# before comparison.
TYPOGRAPHIC_FOLDS = {
    "’": "'",  # right single quote
    "‘": "'",  # left single quote
    "‛": "'",  # single high-reversed-9 quote
    "′": "'",  # prime
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',  # low double quote
    "″": '"',  # double prime
    "—": "-",  # em dash
    "–": "-",  # en dash
    "−": "-",  # minus sign
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
}
_TYPOGRAPHIC_TABLE = {ord(key): value for key, value in TYPOGRAPHIC_FOLDS.items()}
TRAILING_URL_RE = re.compile(r"(?:,\s*|\s+)(https?://\S+)\s*$")
LINK_TEXTS = ("Link", "Lien", "ലിങ്ക്", "ਲਿੰਕ", "लिंक", "Enlace", "Collegamento")


def canonical_value(value: str) -> str:
    """Decode the CSV export representation and normalize visible whitespace."""
    return normalize_text(value.replace('\\"', '"'))


def normalize_text(value: str) -> str:
    """Fold typographic variants and collapse whitespace for text equivalence.

    Applied identically to abstract labels and to rendered page text so that
    typographic-only differences (curly vs straight quotes, em dash vs hyphen,
    non-breaking spaces) are not reported as content drift.
    """
    folded = unicodedata.normalize("NFC", value).translate(_TYPOGRAPHIC_TABLE)
    return " ".join(folded.split())


def rendered_equivalent_values(value: str) -> set[str]:
    """Return visible-text forms equivalent to a source label.

    CV labels store the concrete URL in Wikibase, while rendered CV pages use
    the long-standing visible convention ``(<a>Link</a>)``.
    """
    result = {value}
    match = TRAILING_URL_RE.search(value)
    if match:
        prefix = value[:match.start()].rstrip(" ,")
        result.update(f"{prefix} ({link_text})" for link_text in LINK_TEXTS)
    return result


class Bindings(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.qids: list[tuple[str, str]] = []
        self.call_depth = 0

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if tag == "q-call":
            self.call_depth += 1
        if self.call_depth:
            return
        for kind in ("data-content", "data-entity"):
            value = values.get(kind, "")
            if value.startswith("local:"):
                self.qids.append((kind, value.removeprefix("local:")))
        for name, value in values.items():
            # `data-content-alt` and friends bind an attribute rather than a
            # text node; the value they carry is still content and still has to
            # round-trip.
            if not name.startswith(CONTENT_ATTRIBUTE_PREFIX):
                continue
            if name.removeprefix(CONTENT_ATTRIBUTE_PREFIX) not in BINDABLE_ATTRIBUTES:
                continue
            if (value or "").startswith("local:"):
                self.qids.append((name, value.removeprefix("local:")))

    def handle_endtag(self, tag) -> None:
        if tag == "q-call":
            self.call_depth -= 1


class RenderedAttributes(HTMLParser):
    """Collect the values of every bindable attribute on a rendered page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if name in BINDABLE_ATTRIBUTES and (value or "").strip():
                self.values.append(normalize_text(value))

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)


class RenderedBoundText(HTMLParser):
    """Collect visible text inside rendered Q315-owned elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[bool, list[str]]] = []
        self.values: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        starts_bound = (values.get("data-q315-source") or "").startswith("local:")
        active = starts_bound or bool(self.stack and self.stack[-1][0])
        self.stack.append((active, []))

    def handle_endtag(self, tag) -> None:
        if not self.stack:
            return
        active, parts = self.stack.pop()
        text = normalize_text("".join(parts))
        if active and text:
            if self.stack and self.stack[-1][0]:
                self.stack[-1][1].append(text)
            else:
                self.values.append(text)

    def handle_data(self, data) -> None:
        if self.stack and self.stack[-1][0]:
            self.stack[-1][1].append(data)


def labels(data_dir: Path) -> dict[str, dict[str, str]]:
    result = {}
    with (data_dir / "labels-wikibase.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            result[row["identifier"]] = row
    return result


def bindings(path: Path) -> list[tuple[str, str]]:
    parser = Bindings()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.qids


def rendered_bound_values(path: Path) -> list[str]:
    parser = RenderedBoundText()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.values


def rendered_attribute_values(path: Path) -> list[str]:
    parser = RenderedAttributes()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.values


def verify(
    repo_root: Path,
    data_dir: Path,
    sources: list[tuple[str, Path]],
) -> dict:
    label_rows = labels(data_dir)
    pages = []
    mismatches = []
    for page_qid, relative in sources:
        abstract = repo_root / relative
        page_bindings = bindings(abstract)
        targets = alternate_pages(repo_root, abstract)
        for language, target in zip(LANGUAGES, targets):
            available = Counter(
                normalize_text(value) for value in slots(target).values()
            )
            available.update(rendered_bound_values(target))
            available.update(rendered_attribute_values(target))
            missing = []
            unresolved = []
            expected = Counter()
            for kind, qid in page_bindings:
                row = label_rows.get(qid, {})
                itemtype = row.get("itemtype", "").strip()
                if itemtype in COMPOSED_RESULT_ITEMTYPES:
                    # Function-composed result: verified by evaluating its
                    # constructor, not by matching the result entity's label.
                    continue
                content_kind = kind == "data-content" or kind.startswith(
                    CONTENT_ATTRIBUTE_PREFIX
                )
                wrong_type = (content_kind and itemtype and itemtype != "Q3185") or (
                    kind == "data-entity" and itemtype == "Q3185"
                )
                # DirectTextSlots normalizes all HTML whitespace (including
                # non-breaking spaces), so normalize labels identically before
                # comparing the canonical expectation with rendered text.
                value = canonical_value(row.get(language, ""))
                if not value or wrong_type:
                    unresolved.append(
                        {
                            "qid": qid,
                            "kind": kind,
                            "itemtype": itemtype,
                            "reason": "wrong-itemtype" if wrong_type else "missing-label",
                        }
                    )
                else:
                    expected[value] += 1
            for value, count in expected.items():
                found = max(available[equivalent] for equivalent in rendered_equivalent_values(value))
                if found < count:
                    missing.append(
                        {
                            "text": value,
                            "expected": count,
                            "found": found,
                        }
                    )
            entry = {
                "page_qid": page_qid,
                "language": language,
                "target": target.relative_to(repo_root).as_posix(),
                "missing_rendered_values": missing,
                "unresolved_qids": unresolved,
            }
            pages.append(entry)
            if missing or unresolved:
                mismatches.append(entry)
    return {
        "schema_version": 1,
        "status": "equivalent" if not mismatches else "mismatch",
        "checks": pages,
        "mismatch_count": len(mismatches),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--page",
        default="",
        help="restrict verification to a single abstract page QID",
    )
    parser.add_argument(
        "--max-mismatches",
        type=int,
        help=(
            "fail only when mismatch count exceeds this known structural "
            "baseline (default: require complete equivalence)"
        ),
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    report = verify(
        repo_root, args.data_dir.resolve(), page_sources(repo_root, args.page)
    )
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Round-trip status: {report['status']}; "
        f"language-page mismatches: {report['mismatch_count']}"
    )
    if args.max_mismatches is not None:
        return 0 if report["mismatch_count"] <= args.max_mismatches else 1
    return 0 if report["status"] == "equivalent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
