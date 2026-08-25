#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Push translated prose back to a Wikibase that only holds the English.

This is the counterpart of ``normalize_untranslatable_names.py``. That tool
flattens *names* -- proper nouns, which must read identically everywhere. This
one restores *prose*: intro sentences, section blurbs and captions, which must
not. Where ``labels-wikibase.csv`` holds a real translation and the live item
holds the English in that language, the repo is right and the Wikibase is stale.

The site renders from the snapshot, so such an item looks correct until someone
re-runs ``fetch_wikibase_labels.py``, which would overwrite the translation with
the English and regress every page bound to it.

Only a language whose live value duplicates the live English is touched, so a
genuinely different translation is never overwritten. ``P40`` statements are
replaced in place by id, preserving statement counts, so no language ends up
with two values. Nothing is written without ``--apply``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from content_update import wikibase_label_text
from paths import REPO_ROOT
from wikibase_api import DEFAULT_API, WikibaseClient
from wikibase_write import load_env

from languages import ORDER as LANGUAGES

from normalize_untranslatable_names import sign_in, write_with_retry

LABELS_CSV = HERE / "data" / "labels-wikibase.csv"


def snapshot(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return {row["identifier"]: row for row in csv.DictReader(handle)}


def monolingual_texts(entity: dict) -> dict[str, str]:
    """The item's P40 store, which is where the content actually lives."""
    texts = {}
    for claim in entity.get("claims", {}).get("P40", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("language"):
            texts[value["language"]] = value.get("text", "")
    return texts


def flattened_languages(entity: dict, row: dict[str, str]) -> dict[str, str]:
    """Languages where the live item repeats its English and the repo does not.

    The comparison is against the English *P40* value, not the English label: a
    label can be a stale placeholder (``Q4653``'s reads
    ``M27DF4F7F9C39 abstract sentence``) while P40 holds the real prose, and it
    is P40 that ``fetch_wikibase_labels.py`` falls back to.
    """
    texts = monolingual_texts(entity)
    labels = {
        language: value.get("value", "")
        for language, value in entity.get("labels", {}).items()
    }
    english_text = texts.get("en") or labels.get("en", "")
    english_label = labels.get("en") or texts.get("en", "")
    repo_english = row.get("en", "")
    if not english_text:
        return {}
    restore = {}
    for language in LANGUAGES:
        if language == "en":
            continue
        wanted = row.get(language, "").strip()
        if not wanted or (repo_english and wanted == repo_english):
            continue
        # Either store can be flattened on its own: some items carry an English
        # label over a translated P40, others a translated label over English P40.
        flattened = (
            texts.get(language) == english_text
            or labels.get(language) == english_label
            or labels.get(language) == english_text
        )
        if flattened and wanted != texts.get(language):
            restore[language] = wanted
        elif flattened and wanted != labels.get(language):
            restore[language] = wanted
    return restore


def corrections(entity: dict, restore: dict[str, str]) -> dict:
    """Label and P40 changes that put each translation back on one item."""
    data: dict = {}
    labels = {
        language: {"language": language, "value": wikibase_label_text(value)}
        for language, value in restore.items()
        if entity.get("labels", {}).get(language, {}).get("value")
        != wikibase_label_text(value)
    }
    if labels:
        data["labels"] = labels

    claims = []
    for claim in entity.get("claims", {}).get("P40", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        language = value.get("language")
        if language in restore and value.get("text") != restore[language]:
            replacement = json.loads(json.dumps(claim))
            replacement["mainsnak"]["datavalue"]["value"]["text"] = restore[language]
            claims.append(replacement)
    if claims:
        data["claims"] = claims
    return data


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform writes")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--api", default=None)
    parser.add_argument("--labels", type=Path, default=LABELS_CSV)
    parser.add_argument("--pause", type=float, default=0.5)
    parser.add_argument(
        "--summary",
        default="Restore the translated content the repository snapshot holds",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    rows = snapshot(args.labels)

    load_env(args.env_file)
    client = WikibaseClient(
        args.api or os.getenv("WIKIBASE_API", DEFAULT_API),
        pause=args.pause if args.apply else 0,
    )
    if args.apply:
        sign_in(client)

    qids = sorted(rows, key=lambda qid: int(qid[1:]) if qid[1:].isdigit() else 0)
    changed = label_count = claim_count = 0
    failed: list[str] = []
    for start in range(0, len(qids), 50):
        batch = client.entities(qids[start : start + 50])
        for qid, entity in batch.items():
            if "missing" in entity:
                continue
            restore = flattened_languages(entity, rows[qid])
            if not restore:
                continue
            data = corrections(entity, restore)
            if not data:
                continue
            changed += 1
            label_count += len(data.get("labels", {}))
            claim_count += len(data.get("claims", []))
            print(f"{qid}: restoring {', '.join(sorted(restore))}")
            for language in sorted(restore):
                print(f"    {language}: {restore[language][:70]!r}")
            if args.apply and not write_with_retry(client, qid, data, args.summary):
                failed.append(qid)

    print(
        f"\n{'Restored' if args.apply else 'Would restore'} {changed} item(s) of "
        f"{len(qids)} checked; {label_count} label(s), {claim_count} P40 value(s)."
    )
    if failed:
        print(
            f"{len(failed)} item(s) could not be written: {', '.join(failed)}",
            file=sys.stderr,
        )
        return 1
    if not args.apply and changed:
        print("Dry run only; pass --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
