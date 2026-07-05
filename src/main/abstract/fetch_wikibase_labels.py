#!/usr/bin/env python3
"""Build labels-wikibase.csv directly from the Wikibase ``wbgetentities`` API.

The SPARQL export (``all-multilingual-labels.rq``) times out on the endpoint and
returns partial, value-misaligned results, so items are dropped and labels land
in the wrong rows. The primary-database API is reliable and paginates cleanly, so
this fetcher reproduces the same CSV schema authoritatively.

Items fetched are the union of every identifier already in the current export and
every QID bound in a Q315 template (``data-content``/``data-entity``), so bound
items dropped by the broken export are recovered. ``itemtype`` is the item's
first ``P8`` value, matching the export's column.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import abstract_sources
from abstract.prepare_travel_content import LANGUAGES

DEFAULT_DATA = DEFAULT_DATA_DIR
API = "https://jsamwrites.wikibase.cloud/w/api.php"
QID = re.compile(r"Q[1-9][0-9]*")
# Composed paragraph (Q3835) and sentence (Q3836) types take precedence over the
# generic content type (Q3185) when an item carries several P8 values.
COMPOSED_TYPES = frozenset({"Q3835", "Q3836"})


class _Bound(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.qids: set[str] = set()

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        for attr in ("data-content", "data-entity"):
            value = values.get(attr) or ""
            if value.startswith("local:") and QID.fullmatch(value.removeprefix("local:")):
                self.qids.add(value.removeprefix("local:"))


def bound_qids(repo_root: Path) -> set[str]:
    result: set[str] = set()
    for _, relative in abstract_sources(repo_root):
        parser = _Bound()
        parser.feed((repo_root / relative).read_text(encoding="utf-8"))
        result |= parser.qids
    return result


def existing_identifiers(data_dir: Path) -> set[str]:
    path = data_dir / "labels-wikibase.csv"
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {
            row["identifier"].strip()
            for row in csv.DictReader(source)
            if QID.fullmatch(row.get("identifier", "").strip())
        }


def fetch(ids: list[str], pause: float) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "labels|claims",
                "languages": "|".join(LANGUAGES),
                "format": "json",
            }
        )
        request = urllib.request.Request(
            f"{API}?{query}", headers={"User-Agent": "Q315-label-fetcher/1.0"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            entities = json.load(response)["entities"]
        for qid, entity in entities.items():
            if "missing" in entity:
                continue
            labels = {
                language: entity.get("labels", {}).get(language, {}).get("value", "")
                for language in LANGUAGES
            }
            p8 = [
                claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                for claim in entity.get("claims", {}).get("P8", [])
            ]
            p8 = [value for value in p8 if value]
            # A composed paragraph/sentence carries both Q3185 and Q3835/Q3836.
            # The composed type must win so the renderers treat it as composed
            # (rendered by render_abstract) and never overwrite it with a label.
            composed = next((value for value in p8 if value in COMPOSED_TYPES), "")
            itemtype = composed or (p8[0] if p8 else "")
            result[qid] = {"identifier": qid, "itemtype": itemtype, **labels}
        if pause:
            time.sleep(pause)
        print(f"  fetched {min(start + 50, len(ids))}/{len(ids)}", file=sys.stderr)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_DATA_DIR / "labels-wikibase.csv",
        help="output CSV path (default: the canonical repo label store)",
    )
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    ids = sorted(
        existing_identifiers(args.data_dir.resolve()) | bound_qids(repo_root),
        key=lambda value: int(value[1:]),
    )
    print(f"Fetching {len(ids)} items from {API}", file=sys.stderr)
    rows = fetch(ids, args.pause)
    fields = ("identifier", "itemtype", *LANGUAGES)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        for qid in ids:
            if qid in rows:
                writer.writerow(rows[qid])
    print(f"Wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
