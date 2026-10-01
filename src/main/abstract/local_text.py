#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Text the pages render but the Wikibase deliberately does not hold.

Wikibase Cloud requires every piece of structured data to be in the public
domain or released under CC0. A quotation by an author whose work is still under
copyright cannot be released that way, so its item in the Wikibase keeps only
metadata -- a descriptive label, its creator and where the text is published --
and the quotation itself stays in ``data/content-updates/quotes.csv``, on the
rows marked ``text_in_wikibase=no``.

``labels-wikibase.csv`` remains an exact mirror of the live Wikibase. Every tool
that renders or verifies *page text* overlays this repository-held text on top of
it with :func:`overlay`; the tools that synchronise *with* the Wikibase must not,
and use :func:`local_text_qids` to leave these items alone.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from languages import ORDER as LANGUAGES
from paths import REPO_ROOT

QUOTES_CSV = REPO_ROOT / "data/content-updates/quotes.csv"

# An atomic content component: rendered by substituting its text into a slot,
# never composed from part items.
LOCAL_TEXT_ITEMTYPE = "Q3185"


def text_in_wikibase(row: dict[str, str]) -> bool:
    """Whether a quotes.csv row's text may be stored in the Wikibase."""
    return row.get("text_in_wikibase", "").strip().lower() != "no"


def local_text(path: Path = QUOTES_CSV) -> dict[str, dict[str, str]]:
    """Map each repository-held item to its text in every language.

    Quotations are never translated, so a language without its own
    ``quote_<language>`` column takes the original.
    """
    if not path.exists():
        return {}
    result: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = row.get("local_qid", "").strip()
            if not qid or text_in_wikibase(row):
                continue
            original = row.get("quote", "")
            # CSV values extracted from indented HTML keep their line breaks.
            result[qid] = {
                language: " ".join(
                    (row.get(f"quote_{language}") or original).split()
                )
                for language in LANGUAGES
            }
    return result


def local_text_qids(path: Path = QUOTES_CSV) -> set[str]:
    return set(local_text(path))


def overlay(
    labels: dict[str, dict[str, str]], path: Path = QUOTES_CSV
) -> dict[str, dict[str, str]]:
    """Return ``labels`` with repository-held text in place of the Wikibase label."""
    for qid, texts in local_text(path).items():
        row = dict(labels.get(qid, {"identifier": qid}))
        row.update(texts)
        row["itemtype"] = LOCAL_TEXT_ITEMTYPE
        labels[qid] = row
    return labels
