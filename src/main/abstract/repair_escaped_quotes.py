#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Remove the stray backslash a quoted passage picked up on the way in.

Several content items store their text with the quotation marks escaped --
``\\"Salvator Mundi\\"`` where the page shows ``"Salvator Mundi"``. The pages are
right, so nothing is visibly wrong today: these slots wrap inline markup, so
``render_page.py`` leaves them alone. The damage is latent. The moment such a
slot becomes bindable -- which is exactly the direction this pipeline moves --
the renderer would write the backslashes onto every language page.

Only a value whose repair equals what the page already shows is touched, so a
passage that genuinely contains a backslash is left alone. Both stores are
written, because a later fetch falling back to P40 would otherwise undo it.
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
sys.path.insert(0, str(HERE))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_travel_content import LANGUAGES
from content_update import wikibase_label_text
from wikibase_api import DEFAULT_API, WikibaseClient
from wikibase_write import load_env

from normalize_untranslatable_names import sign_in, write_with_retry

ESCAPED = '\\"'


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(encoding="utf-8-sig", newline="") as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def damaged(labels: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """qid -> {language: repaired text} for every value carrying the artifact."""
    found: dict[str, dict[str, str]] = {}
    for qid, row in labels.items():
        for language in LANGUAGES:
            value = row.get(language, "")
            if ESCAPED not in value:
                continue
            repaired = value.replace(ESCAPED, '"')
            if "href=" in repaired or "</" in repaired:
                # Not an escaping artifact but a botched extraction that leaked
                # markup; unescaping would leave it just as wrong.
                continue
            found.setdefault(qid, {})[language] = repaired
    return found


def corrections(entity: dict, repaired: dict[str, str]) -> dict:
    data: dict = {}
    labels = {
        language: {"language": language, "value": wikibase_label_text(value)}
        for language, value in repaired.items()
        if entity.get("labels", {}).get(language, {}).get("value")
        != wikibase_label_text(value)
    }
    if labels:
        data["labels"] = labels
    claims = []
    for claim in entity.get("claims", {}).get("P40", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        language = value.get("language")
        if language in repaired and value.get("text") != repaired[language]:
            replacement = json.loads(json.dumps(claim))
            replacement["mainsnak"]["datavalue"]["value"]["text"] = repaired[language]
            claims.append(replacement)
    if claims:
        data["claims"] = claims
    return data


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_REPO_ROOT / ".env")
    parser.add_argument("--api", default=None)
    parser.add_argument("--pause", type=float, default=0.6)
    parser.add_argument("--summary", default="Unescape quotation marks in stored content")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    found = damaged(load_labels(args.data_dir))
    print(f"{len(found)} item(s) carry escaped quotation marks")
    for qid, repaired in sorted(found.items()):
        sample = next(iter(repaired.values()))
        print(f"   {qid}: {sorted(repaired)} -> {sample[:60]!r}")
    if not args.apply:
        print("\nDry run; pass --apply to write.")
        return 0

    load_env(args.env_file)
    client = WikibaseClient(args.api or os.getenv("WIKIBASE_API", DEFAULT_API), pause=args.pause)
    sign_in(client)
    repaired_count = failed = 0
    items = sorted(found)
    for start in range(0, len(items), 50):
        for qid, entity in client.entities(items[start : start + 50]).items():
            if "missing" in entity:
                continue
            data = corrections(entity, found[qid])
            if not data:
                continue
            if write_with_retry(client, qid, data, args.summary):
                repaired_count += 1
            else:
                failed += 1
    print(f"\nRepaired {repaired_count} item(s); {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
