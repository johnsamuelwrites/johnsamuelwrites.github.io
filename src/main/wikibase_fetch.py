#!/usr/bin/env python3
"""Fetch Wikibase entities into a deterministic JSON snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from wikibase_api import DEFAULT_API, WikibaseClient


def read_ids(values: list[str], files: list[Path]) -> list[str]:
    ids = list(values)
    for path in files:
        ids.extend(
            token
            for line in path.read_text(encoding="utf-8").splitlines()
            if (token := line.strip()) and not token.startswith("#")
        )
    return list(dict.fromkeys(ids))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--entity", action="append", default=[])
    parser.add_argument("--entity-file", action="append", type=Path, default=[])
    parser.add_argument(
        "--all", action="store_true",
        help="fetch every item and property (can be slow)",
    )
    args = parser.parse_args(argv)
    client = WikibaseClient(args.api)
    ids = read_ids(args.entity, args.entity_file)
    if args.all:
        ids.extend(client.all_entity_ids((0, 120)))
        ids = list(dict.fromkeys(ids))
    if not ids:
        parser.error("supply --entity, --entity-file, or --all")
    entities = client.entities(ids)
    missing = sorted(set(ids) - set(entities))
    snapshot = {
        "schema_version": 1,
        "source": args.api,
        "entities": dict(sorted(entities.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entities)} entities to {args.output}")
    if missing:
        print(f"Warning: {len(missing)} IDs were not returned")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
