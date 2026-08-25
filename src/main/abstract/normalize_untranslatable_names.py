#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Keep names and titles in their original form in every language.

Quotes, book titles, author names, film titles and music titles are proper
nouns: they must read identically in all eight languages. A translation or
transliteration stored against one of them is a data error, not a translation.

Two stores hold the value and both have to agree with the content-update CSVs:

``labels``
    what ``labels-wikibase.csv`` exports and therefore what ``render_page.py``
    writes into the pages. A translated label is visible on the site.
``P40``
    the abstract content model's monolingual store. A translated P40 value is
    invisible while the label is intact, but ``fetch_wikibase_labels.py`` falls
    back to P40 whenever a label is empty or truncated (labels are capped at 250
    characters), so a long title silently starts rendering its translation.

Statements are replaced in place, preserving statement ids and counts, so this
never leaves a second P40 value for a language behind.

Nothing is written without ``--apply``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from content_update import FAMILIES, read_rows, split_qids, wikibase_label_text
from paths import REPO_ROOT
from wikibase_api import DEFAULT_API, WikibaseClient, WikibaseError
from wikibase_write import load_env

from languages import ORDER as LANGUAGES

# (qid column, value column) pairs whose value must never be translated.
UNTRANSLATABLE = {
    "books": (("local_qid", "name"), ("creator_qid", "creator")),
    "films": (("local_qid", "name"),),
    "music": (("local_qid", "name"),),
    "quotes": (("attribution_qid", "attribution"), ("local_qid", "quote")),
}

# A split quote is a composed item whose text lives in its part items, so the
# CSV's whole-quote value belongs to neither. Composed wrappers are skipped and
# their parts take their canonical form from their own English value instead.
COMPOSED_ITEMTYPES = frozenset({"Q3835", "Q3836"})

# Q3900 is the Elska book title "Berlin, Germany" and also the place Berlin on
# Q315/Q3062/Q3025/Q3074/Q3132.html, where the French "Berlin, Allemagne" is
# correct. One item cannot satisfy both rules; it needs its own content item for
# the book before either use can be corrected.
EXCLUDED = {"Q3900"}

# Wikibase rejects two items sharing a label *and* a description in the same
# language, and every abstract content item is created with the same generic
# description. Two different works can legitimately share a title -- "Queen" is
# both a band and a film -- so the loser of that collision gets its QID added to
# its description. Descriptions are metadata and are never rendered.
DISAMBIGUATED_DESCRIPTION = (
    "language-independent content component used by an abstract page ({qid})"
)


def composed_qids() -> set[str]:
    path = REPO_ROOT / "src/main/abstract/data/labels-wikibase.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {
            row["identifier"]
            for row in csv.DictReader(source)
            if row.get("itemtype") in COMPOSED_ITEMTYPES
        }


def split_quote_parts() -> set[str]:
    """Part items of split quotes, whose canonical form is their own English text."""
    family = FAMILIES["quotes"]
    rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
    parts: set[str] = set()
    for row in rows:
        parts.update(split_qids(row.data.get("part_qids", "")))
    return parts


def english_value(entity: dict) -> str:
    for claim in entity.get("claims", {}).get("P40", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("language") == "en" and value.get("text"):
            return value["text"]
    return entity.get("labels", {}).get("en", {}).get("value", "")


def canonical_values() -> tuple[dict[str, str], list[str]]:
    """Map each QID to the single form it must show in every language."""
    values: dict[str, str] = {}
    conflicts: list[str] = []
    composed = composed_qids()
    for family_name, columns in UNTRANSLATABLE.items():
        family = FAMILIES[family_name]
        rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
        for row in rows:
            for qid_column, value_column in columns:
                qid = row.data.get(qid_column, "").strip()
                # CSV values extracted from indented HTML keep their line breaks.
                value = " ".join(row.data.get(value_column, "").split())
                if not qid or not value or qid in EXCLUDED or qid in composed:
                    continue
                if values.get(qid, value) != value:
                    conflicts.append(f"{qid}: {values[qid]!r} vs {value!r}")
                values[qid] = value
    return values, conflicts


def corrections(entity: dict, wanted: str) -> dict:
    """Label and P40 changes needed to bring one item to its canonical value."""
    data: dict = {}
    label = wikibase_label_text(wanted)
    labels = {
        language: {"language": language, "value": label}
        for language in LANGUAGES
        if entity.get("labels", {}).get(language, {}).get("value") != label
    }
    if labels:
        data["labels"] = labels

    claims = []
    for claim in entity.get("claims", {}).get("P40", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("language") in LANGUAGES and value.get("text") != wanted:
            replacement = json.loads(json.dumps(claim))
            replacement["mainsnak"]["datavalue"]["value"]["text"] = wanted
            claims.append(replacement)
    if claims:
        data["claims"] = claims
    return data


def sign_in(client: WikibaseClient) -> None:
    username, password = os.getenv("WIKIBASE_USERNAME"), os.getenv("WIKIBASE_PASSWORD")
    if not username or not password:
        raise SystemExit("WIKIBASE_USERNAME and WIKIBASE_PASSWORD are required")
    client.login(username, password)


def write_with_retry(client: WikibaseClient, qid: str, data: dict, summary: str) -> bool:
    """Write one item, surviving both of the ways a long run gets interrupted.

    The edit throttle reports only a generic ``failed-save``, so a failure is
    retried before it is believed. The login session also expires part-way
    through a run of this length, and that surfaces as ``assertuserfailed`` on
    every subsequent write -- retrying alone never recovers, so the session is
    re-established first. An item that still fails is reported and skipped rather
    than ending the run: the tool only edits items that still differ, so
    re-running resumes where it stopped.
    """
    disambiguated = False
    for attempt, delay in enumerate((5, 15, 45, 0)):
        try:
            client.edit_entity(data, entity_id=qid, summary=summary)
            return True
        except WikibaseError as error:
            if attempt == 3:
                print(f"  {qid}: giving up: {error}", file=sys.stderr)
                return False
            if "already has label" in str(error) and not disambiguated:
                print(
                    f"  {qid}: label already used by another item; "
                    "disambiguating its description",
                    file=sys.stderr,
                )
                data["descriptions"] = {
                    "en": {
                        "language": "en",
                        "value": DISAMBIGUATED_DESCRIPTION.format(qid=qid),
                    }
                }
                disambiguated = True
                continue
            if "assertuserfailed" in str(error):
                print(f"  {qid}: session expired; signing in again", file=sys.stderr)
                try:
                    sign_in(client)
                    continue
                except Exception as login_error:  # noqa: BLE001 - reported, then retried
                    print(f"  sign-in failed: {login_error}", file=sys.stderr)
            else:
                print(f"  {qid}: {error}; retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform writes")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--api", default=None)
    parser.add_argument("--limit", type=int, default=0, help="stop after N items")
    parser.add_argument(
        "--pause", type=float, default=0.5, help="seconds between writes"
    )
    parser.add_argument(
        "--summary",
        default="Names and titles keep their original form in every language",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    wanted, conflicts = canonical_values()
    for conflict in conflicts:
        print(f"conflicting canonical value for {conflict}", file=sys.stderr)
    if conflicts:
        return 1

    load_env(args.env_file)
    client = WikibaseClient(
        args.api or os.getenv("WIKIBASE_API", DEFAULT_API),
        pause=args.pause if args.apply else 0,
    )
    if args.apply:
        sign_in(client)

    parts = split_quote_parts() - EXCLUDED
    qids = sorted(set(wanted) | parts, key=lambda qid: int(qid[1:]))
    changed = label_count = claim_count = 0
    failed: list[str] = []
    for start in range(0, len(qids), 50):
        for qid, entity in client.entities(qids[start : start + 50]).items():
            if "missing" in entity:
                continue
            value = wanted.get(qid) or english_value(entity)
            if not value:
                print(f"{qid}: no canonical value available; skipped", file=sys.stderr)
                continue
            data = corrections(entity, value)
            if not data:
                continue
            changed += 1
            label_count += len(data.get("labels", {}))
            claim_count += len(data.get("claims", []))
            print(
                f"{qid}: {value[:60]!r} "
                f"labels={len(data.get('labels', {}))} p40={len(data.get('claims', []))}"
            )
            if args.apply and not write_with_retry(client, qid, data, args.summary):
                failed.append(qid)
            if args.limit and changed >= args.limit:
                break
        if args.limit and changed >= args.limit:
            break

    print(
        f"\n{'Applied' if args.apply else 'Would change'} {changed} item(s) of {len(qids)} checked; "
        f"{label_count} label(s), {claim_count} P40 value(s)."
    )
    if failed:
        print(f"{len(failed)} item(s) could not be written: {', '.join(failed)}", file=sys.stderr)
        print("Re-run to retry them; corrected items are skipped automatically.", file=sys.stderr)
    if not args.apply:
        print("Dry run only; pass --apply to write.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
