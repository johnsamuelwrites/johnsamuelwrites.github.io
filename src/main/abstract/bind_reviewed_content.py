#!/usr/bin/env python3
"""Bind reviewed QIDs from missing-content-review.csv into abstract HTML."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.bind_travel_manifest import bind_page
from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import DEFAULT_REVIEW


def load_review(path: Path) -> dict[Path, dict[tuple[str, str, str, int], str]]:
    pages: dict[Path, dict[tuple[str, str, str, int], str]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = row["qid"].strip()
            if not qid:
                continue
            if not re.fullmatch(r"Q[1-9][0-9]*", qid):
                raise ValueError(f"{path}: invalid QID {qid!r}")
            key = (
                row["tag"].strip(),
                row["class"].strip(),
                row["role"].strip(),
                int(row["occurrence"]),
            )
            pages[Path(row["path"].strip())][key] = qid
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace an existing local data-content binding at reviewed slots",
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    try:
        pages = load_review(args.review)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    changed = 0
    for relative, bindings in pages.items():
        _, output, errors = bind_page(
            root,
            relative.stem,
            relative,
            bindings,
            replace_existing=args.replace_existing,
        )
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        path = root / relative
        source = path.read_text(encoding="utf-8")
        if source != output:
            changed += 1
            if not args.check:
                path.write_text(output, encoding="utf-8")
    if args.check and changed:
        print(f"ERROR: {changed} abstract page(s) are not bound", file=sys.stderr)
        return 1
    print(f"{'Validated' if args.check else 'Bound'} {len(pages)} page(s); {changed} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
