#!/usr/bin/env python3
"""Prepare dedicated multilingual content items for the detailed CV.

The concise and detailed CVs intentionally differ: the concise page may use
``et al.``, while the detailed page retains every collaborator.  Reusing a
content item between those representations makes one of them lossy.  This
tool extracts aligned text from all eight detailed-CV pages, deduplicates
identical multilingual tuples, and emits both create operations and a binding
review.  Existing composed paragraphs remain owned by ``render_abstract``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_content_corrections import bound_slots
from abstract.prepare_missing_content import alternate_pages
from abstract.prepare_travel_content import LANGUAGES, quote, slots
from abstract.verify_content_roundtrip import COMPOSED_RESULT_ITEMTYPES, labels

TEMPLATE = Path("Q315/Q3636/Q3646.html")


def prepare(repo_root: Path, data_dir: Path) -> tuple[list[dict[str, str]], list[tuple[str, ...]]]:
    template = (repo_root / TEMPLATE).resolve()
    label_rows = labels(data_dir)
    localized = [
        slots(path) for path in alternate_pages(repo_root, template)
    ]
    rows: list[dict[str, str]] = []
    values: list[tuple[str, ...]] = []
    value_index: dict[tuple[str, ...], int] = {}
    for key, (kind, old_qid) in bound_slots(template).items():
        # Paragraph signatures are structurally identical across the eight
        # detailed CVs. Global anchor/list occurrence numbers are not: menus
        # contain language-specific links and must retain their established
        # bindings rather than being paired by a misleading global index.
        if kind != "data-content" or key[0] != "p":
            continue
        itemtype = label_rows.get(old_qid, {}).get("itemtype", "").strip()
        if itemtype in COMPOSED_RESULT_ITEMTYPES:
            continue
        translations = tuple(page.get(key, "").strip() for page in localized)
        if not all(translations):
            continue
        if any(len(value) > 250 for value in translations):
            raise ValueError(f"{old_qid} at {key} exceeds the Wikibase label limit")
        index = value_index.get(translations)
        if index is None:
            index = len(values) + 1
            value_index[translations] = index
            values.append(translations)
        tag, class_name, role, occurrence = key
        rows.append(
            {
                "page": "Q3646",
                "path": TEMPLATE.as_posix(),
                "tag": tag,
                "class": class_name,
                "role": role,
                "occurrence": str(occurrence),
                "old_qid": old_qid,
                "create_index": str(index),
                "qid": "",
            }
        )
    return rows, values


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ("page", "path", "tag", "class", "role", "occurrence",
              "old_qid", "create_index", "qid")
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_quickstatements(
    path: Path, values: list[tuple[str, ...]], skip_items: int = 0
) -> None:
    blocks = []
    for index, translations in enumerate(values, 1):
        if index <= skip_items:
            continue
        block = ["CREATE"]
        block.extend(
            f'LAST|L{language}|"{quote(value)}"'
            for language, value in zip(LANGUAGES, translations)
        )
        block.extend(
            f'LAST|P40|{language}:"{quote(value)}"'
            for language, value in zip(LANGUAGES, translations)
        )
        block.extend(
            (
                f'LAST|Den|"detailed CV content component {index}"',
                "LAST|P8|Q3185",
            )
        )
        blocks.append("\n".join(block))
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def add_created_qids(review: Path, write_log: Path) -> None:
    created = [
        match.group(1)
        for line in write_log.read_text(encoding="utf-8").splitlines()
        if (match := re.fullmatch(r"Wrote (Q[1-9][0-9]*)", line))
    ]
    with review.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fields = reader.fieldnames or []
    expected = max(int(row["create_index"]) for row in rows)
    if len(created) != expected:
        raise ValueError(f"write log has {len(created)} QIDs; expected {expected}")
    for row in rows:
        row["qid"] = created[int(row["create_index"]) - 1]
    with review.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--quickstatements", type=Path, required=True)
    parser.add_argument("--created-log", type=Path)
    parser.add_argument("--skip-items", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.created_log:
            add_created_qids(args.review, args.created_log)
            print(f"Added created QIDs to {args.review}")
            return 0
        rows, values = prepare(args.repo_root.resolve(), args.data_dir.resolve())
        write_review(args.review, rows)
        write_quickstatements(args.quickstatements, values, args.skip_items)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"Prepared {len(values)} detailed-CV items for "
        f"{len(rows)} bound occurrences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
