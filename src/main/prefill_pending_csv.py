#!/usr/bin/env python3
"""Prefill a pending translation CSV using the shared DB + glossary workflow."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from translation_config import DEFAULT_DB_PATH, DEFAULT_GLOSSARY_DIR, DEFAULT_OUTPUT_DIR
from translate_manager import TranslationManager


def detect_target_lang(csv_path: Path) -> str:
    """Infer the target language from the first row of the CSV."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        first_row = next(reader, None)
    if not first_row or not first_row.get("dest_language"):
        raise ValueError(f"Could not infer target language from {csv_path}")
    return first_row["dest_language"].strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prefill a pending translation CSV using DB + glossary matches."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR) / "missing_es_index.csv",
        help="Path to the CSV file to update.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(DEFAULT_DB_PATH),
        help="Optional translations database path override.",
    )
    parser.add_argument(
        "--target-lang",
        help="Optional target language override. By default, inferred from dest_language in the CSV.",
    )
    parser.add_argument(
        "--glossary-dir",
        type=Path,
        default=Path(DEFAULT_GLOSSARY_DIR),
        help="Directory containing translation_glossary_<lang>.json files.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Only fill empty dest_text values.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    csv_path = args.csv.resolve()
    target_lang = args.target_lang or detect_target_lang(csv_path)

    manager = TranslationManager(
        source_lang="en",
        target_langs=[target_lang],
        db_path=str(args.db_path),
    )

    try:
        glossary_path = args.glossary_dir / f"translation_glossary_{target_lang}.json"
        glossaries = {target_lang: manager.load_glossary(str(glossary_path))}
        stats = manager.prefill_translations_in_csv(
            str(csv_path),
            glossaries,
            overwrite_existing=not args.no_overwrite,
        )
    finally:
        manager.close()

    print(
        f"Updated {stats['updated']} rows in {csv_path} "
        f"({stats['rows']} total rows; db={stats['from_db']}, "
        f"glossary={stats['from_glossary']}, remaining={stats['remaining']}, "
        f"target_lang={target_lang})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
