#!/usr/bin/env python3
"""Fetch a deterministic Wikibase entity snapshot for abstract rendering."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence


DEFAULT_API = "https://jsamwrites.wikibase.cloud/w/api.php"
DEFAULT_ENTITIES = (
    "Q3834", "Q3835", "Q3836", "Q3837", "Q3838",
    "Q3839", "Q3840", "Q3841", "P40", "P41", "P42",
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent / "snapshots" / "Q3062-hero.json"
)


def fetch(api: str, entity_ids: Sequence[str]) -> dict:
    entities = {}
    for start in range(0, len(entity_ids), 50):
        chunk = entity_ids[start : start + 50]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "format": "json",
            }
        )
        request = urllib.request.Request(
            f"{api}?{query}",
            headers={"User-Agent": "Q315-abstract-renderer/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        if payload.get("success") != 1:
            raise ValueError("Wikibase did not return a successful entity response")
        entities.update(payload.get("entities", {}))
    missing = sorted(set(entity_ids) - set(entities))
    if missing:
        raise ValueError(f"Wikibase response omitted: {', '.join(missing)}")
    return {
        "schema_version": 1,
        "source": api,
        "entities": entities,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--entity", action="append", dest="entities")
    parser.add_argument(
        "--source-html",
        type=Path,
        help="include every local QID referenced by a canonical HTML page",
    )
    args = parser.parse_args(argv)
    entities = set(args.entities or DEFAULT_ENTITIES)
    if args.source_html:
        entities.update(re.findall(r"local:(Q[1-9][0-9]*)", args.source_html.read_text()))
        entities.update({"P40", "P41", "P42"})
    ordered = sorted(
        entities, key=lambda value: (value[0], int(value[1:]))
    )
    snapshot = fetch(args.api, ordered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(snapshot['entities'])} entities to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
