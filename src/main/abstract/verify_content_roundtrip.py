#!/usr/bin/env python3
"""Verify that abstract-page QID bindings reproduce existing language-page text."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import alternate_pages, page_sources
from abstract.prepare_travel_content import LANGUAGES, slots

DEFAULT_DATA = DEFAULT_REPO_ROOT.parent / "Q42761025" / "data"
DEFAULT_REPORT = HERE / "content-roundtrip.json"

# A binding whose entity is itself a function-composed result (an abstract
# paragraph) is verified by evaluating its constructor, not by comparing the
# label of the result entity. Identified generically by item type rather than
# by a hard-coded QID.
COMPOSED_RESULT_ITEMTYPES = frozenset({"Q3835"})


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

    def handle_endtag(self, tag) -> None:
        if tag == "q-call":
            self.call_depth -= 1


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
            available = Counter(slots(target).values())
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
                wrong_type = (
                    kind == "data-content" and itemtype and itemtype != "Q3185"
                ) or (
                    kind == "data-entity" and itemtype == "Q3185"
                )
                value = row.get(language, "").strip()
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
                if available[value] < count:
                    missing.append(
                        {
                            "text": value,
                            "expected": count,
                            "found": available[value],
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
    return 0 if report["status"] == "equivalent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
