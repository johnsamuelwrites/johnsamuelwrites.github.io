#!/usr/bin/env python3
"""Build labels-wikibase.csv directly from the Wikibase ``wbgetentities`` API.

The SPARQL export (``all-multilingual-labels.rq``) times out on the endpoint and
returns partial, value-misaligned results, so items are dropped and labels land
in the wrong rows. The primary-database API is reliable and paginates cleanly, so
this fetcher reproduces the same CSV schema authoritatively.

Items fetched are the union of every identifier already in the current export and
every QID bound in a Q315 template (``data-content``/``data-entity``/
``data-content-<attribute>``), so bound
items dropped by the broken export are recovered, and every item created since
the newest one in the export -- an item just imported is neither, and the
binders need its labels before they can bind it.

Runs are incremental: the time of each fetch is kept beside the CSV, and the
next run asks the wiki's recent changes which items were edited or created
since, fetching only those (plus any bound item the CSV lacks) and merging them
into the existing rows. ``--full`` refetches everything; so does a run with no
recorded fetch or one older than the wiki's recent-changes window. ``itemtype`` is the item's
first ``P8`` value, matching the export's column.
"""

from __future__ import annotations

import argparse
import csv
import datetime
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
from abstract.render_page import CONTENT_ATTRIBUTE_PREFIX

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
        for attr, value in values.items():
            # `data-content-alt` and its siblings bind an attribute rather than a
            # text node; those items need labels just as much.
            if attr not in ("data-content", "data-entity") and not attr.startswith(
                CONTENT_ATTRIBUTE_PREFIX
            ):
                continue
            value = value or ""
            if value.startswith("local:") and QID.fullmatch(value.removeprefix("local:")):
                self.qids.add(value.removeprefix("local:"))

    def handle_startendtag(self, tag, attrs) -> None:
        # `<img />` is reported here, and it is the element attribute bindings
        # exist for.
        self.handle_starttag(tag, attrs)


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


ITEM_NAMESPACE = 120


def items_created_after(newest: int, pause: float) -> set[str]:
    """QIDs above ``newest``, listed from the Item namespace."""
    result: set[str] = set()
    params = {
        "action": "query",
        "list": "allpages",
        "apnamespace": str(ITEM_NAMESPACE),
        "aplimit": "500",
        "format": "json",
    }
    while True:
        request = urllib.request.Request(
            f"{API}?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": "Q315-label-fetcher/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        for page in data.get("query", {}).get("allpages", []):
            qid = page["title"].rsplit(":", 1)[-1]
            if QID.fullmatch(qid) and int(qid[1:]) > newest:
                result.add(qid)
        if "continue" not in data:
            return result
        params.update(data["continue"])
        if pause:
            time.sleep(pause)


def truncated(label: str, text: str) -> bool:
    """Whether ``label`` is ``text`` cut to the label length limit.

    A label may legitimately end in "..." ("Paris, Lyon, Marseille..."); it is
    only a truncation when the full P40 text continues it.
    """
    if not label.endswith("..."):
        return False
    stem = label[:-3].rstrip()
    return len(text) > len(stem) and text.startswith(stem) and text != label


# MediaWiki keeps recent changes for 90 days by default; stay well inside it.
INCREMENTAL_WINDOW = datetime.timedelta(days=30)
# Edits saved while a fetch runs must not fall between two runs.
SAFETY_MARGIN = datetime.timedelta(minutes=10)


def state_path(out: Path) -> Path:
    return out.with_name(out.stem + ".fetched.json")


def last_fetch(out: Path) -> datetime.datetime | None:
    path = state_path(out)
    if not path.exists() or not out.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("fetched_at", "")
    return datetime.datetime.fromisoformat(value) if value else None


def changed_items(since: datetime.datetime, pause: float) -> set[str]:
    """Items edited or created on the wiki since ``since``."""
    result: set[str] = set()
    params = {
        "action": "query",
        "list": "recentchanges",
        "rcnamespace": str(ITEM_NAMESPACE),
        "rctype": "edit|new",
        "rcprop": "title",
        "rcdir": "newer",
        "rcstart": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rclimit": "500",
        "format": "json",
    }
    while True:
        request = urllib.request.Request(
            f"{API}?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": "Q315-label-fetcher/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        for change in data.get("query", {}).get("recentchanges", []):
            qid = change["title"].rsplit(":", 1)[-1]
            if QID.fullmatch(qid):
                result.add(qid)
        if "continue" not in data:
            return result
        params.update(data["continue"])
        if pause:
            time.sleep(pause)


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


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
            p40 = {}
            for claim in entity.get("claims", {}).get("P40", []):
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                language = value.get("language", "")
                text = value.get("text", "")
                if language in labels and text:
                    p40[language] = text
            for language, text in p40.items():
                label = labels.get(language, "")
                if not label or truncated(label, text):
                    labels[language] = text
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
    parser.add_argument("--full", action="store_true", help="refetch every item")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    started = datetime.datetime.now(datetime.timezone.utc)
    existing = existing_identifiers(args.data_dir.resolve())
    previous = None if args.full else last_fetch(args.out)
    if previous and started - previous > INCREMENTAL_WINDOW:
        previous = None
    if previous:
        changed = changed_items(previous - SAFETY_MARGIN, args.pause)
        missing_bound = bound_qids(repo_root) - existing
        wanted = changed | missing_bound
        print(
            f"Incremental fetch since {previous:%Y-%m-%d %H:%M} UTC: "
            f"{len(changed)} changed, {len(missing_bound)} bound but missing",
            file=sys.stderr,
        )
        rows = read_rows(args.out)
        rows.update(fetch(sorted(wanted, key=lambda value: int(value[1:])), args.pause))
    else:
        newest = max((int(qid[1:]) for qid in existing), default=0)
        wanted = existing | bound_qids(repo_root) | items_created_after(newest, args.pause)
        print(f"Full fetch of {len(wanted)} items from {API}", file=sys.stderr)
        rows = fetch(sorted(wanted, key=lambda value: int(value[1:])), args.pause)
    fields = ("identifier", "itemtype", *LANGUAGES)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        for qid in sorted(rows, key=lambda value: int(value[1:])):
            writer.writerow({field: rows[qid].get(field, "") for field in fields})
    state_path(args.out).write_text(
        json.dumps({"fetched_at": started.isoformat(timespec="seconds")}) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {args.out} ({len(wanted)} fetched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
