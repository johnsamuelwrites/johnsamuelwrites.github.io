#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Make image descriptions Q315 content, like every other translated string.

An image's ``alt`` is its description for anyone who cannot see it, and it is as
language-specific as any caption. It was the one piece of translated content the
abstract layer could not own: ``render_page.py`` rewrites text nodes, and ``alt``
is an attribute, so the abstract pages carried ``alt=""`` and each language page
kept its own literal string.

``data-content-alt="local:Q..."`` closes that. This tool reads the alt text the
language pages already show, gives each distinct set of eight a content item,
and writes the binding onto the abstract page. After it runs, ``render_page.py``
writes every language's alt from the item, and ``verify_content_roundtrip.py``
checks it like any other bound value.

Slots are matched by the ``(tag, class, role, occurrence)`` signature the
renderer uses, so a page whose languages have drifted structurally is skipped
rather than bound to the wrong image. Nothing is written without ``--apply``,
and the run is resumable: an already-bound slot is left alone.
"""

from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import alternate_pages, page_sources
from abstract.prepare_travel_content import LANGUAGES
from abstract.render_page import _base_signature, base_counts
from content_update import (
    ABSTRACT_CONTENT_ITEM,
    build_wikibase_content_item_data,
    content_item_description,
    is_label_conflict,
)
from wikibase_api import DEFAULT_API, WikibaseClient, WikibaseError
from wikibase_write import load_env

from normalize_untranslatable_names import sign_in, write_with_retry

CONTENT_ITEM_TYPE = "Q3185"


class Images(HTMLParser):
    """``signature -> (alt, src, already_bound)`` for every image on a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts: collections.Counter = collections.Counter()
        self.found: dict[tuple, tuple[str | None, str, str]] = {}

    def handle_starttag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        index = self.counts[base]
        self.counts[base] += 1
        if tag != "img":
            return
        values = dict(attrs)
        self.found[(*base, index)] = (
            values.get("alt"),
            values.get("src", ""),
            (values.get("data-content-alt") or "").removeprefix("local:"),
        )

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)


def images(path: Path) -> dict[tuple, tuple[str | None, str, str]]:
    parser = Images()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.found


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(encoding="utf-8-sig", newline="") as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def existing_by_text(labels: dict[str, dict[str, str]]) -> dict[tuple[str, ...], str]:
    """Content items keyed by their full eight-language text."""
    found: dict[tuple[str, ...], str] = {}
    for qid, row in labels.items():
        if row.get("itemtype", "").strip() != CONTENT_ITEM_TYPE:
            continue
        key = tuple((row.get(language) or "").strip() for language in LANGUAGES)
        if all(key):
            found.setdefault(key, qid)
    return found


def collect(repo_root: Path) -> tuple[list[dict], collections.Counter]:
    """Every abstract image slot whose languages all show alt text."""
    slots: list[dict] = []
    reasons: collections.Counter = collections.Counter()
    for page_qid, relative in page_sources(repo_root):
        abstract = repo_root / relative
        abstract_images = images(abstract)
        if not abstract_images:
            continue
        targets = list(zip(LANGUAGES, alternate_pages(repo_root, abstract)))
        if any(not target or not Path(target).exists() for _language, target in targets):
            reasons["page has no full set of language pages"] += 1
            continue
        abstract_counts = base_counts(abstract.read_text(encoding="utf-8"))
        per_language = {}
        per_language_counts = {}
        for language, target in targets:
            page = Path(target)
            text = page.read_text(encoding="utf-8", errors="replace")
            per_language[language] = images(page)
            per_language_counts[language] = base_counts(text)
        for key, (_alt, src, bound) in sorted(abstract_images.items()):
            base = key[:3]
            # The renderer only aligns a slot by occurrence when both sides hold
            # the same number of same-signature elements, and it decides that per
            # signature rather than per page. Anything else would bind the
            # description of one photograph to another.
            if any(
                per_language_counts[language].get(base) != abstract_counts.get(base)
                for language in LANGUAGES
            ):
                reasons["image signature count differs between languages"] += 1
                continue
            values = {}
            for language in LANGUAGES:
                other = per_language[language].get(key)
                values[language] = (other[0] or "").strip() if other else ""
            if not all(values.values()):
                reasons["image lacks alt text in every language"] += 1
                continue
            slots.append(
                {
                    "page": page_qid,
                    "abstract": abstract,
                    "key": key,
                    "src": src,
                    "bound": bound,
                    "values": values,
                }
            )
    return slots, reasons


def write_binding(path: Path, key: tuple, qid: str) -> bool:
    """Add ``data-content-alt`` to the one image the signature addresses."""
    text = path.read_text(encoding="utf-8")
    parser = Images()
    parser.feed(text)
    if key not in parser.found:
        return False
    # Re-scan for the start tag by counting img occurrences the same way.
    counts: collections.Counter = collections.Counter()
    for match in re.finditer(r"<[a-zA-Z][^>]*>", text):
        tag_text = match.group(0)
        name = re.match(r"<([a-zA-Z0-9]+)", tag_text).group(1).lower()
        attrs = [
            (attr.group(1).lower(), attr.group(2))
            for attr in re.finditer(r'([a-zA-Z-]+)\s*=\s*"([^"]*)"', tag_text)
        ]
        base = _base_signature(name, attrs)
        index = counts[base]
        counts[base] += 1
        if (*base, index) != key or name != "img":
            continue
        if "data-content-alt=" in tag_text:
            return False
        replacement = tag_text[:-1].rstrip()
        closing = "/>" if tag_text.rstrip().endswith("/>") else ">"
        if replacement.endswith("/"):
            replacement = replacement[:-1].rstrip()
        replacement = f'{replacement} data-content-alt="local:{qid}" {closing}'
        path.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")
        return True
    return False


def create_with_retry(client: WikibaseClient, key: tuple[str, ...], summary: str) -> str:
    """Create one content item, surviving the two ways a long run breaks.

    A run this size trips the edit throttle, which reports only a generic
    ``failed-save``, and outlives the login session, which then fails every
    write with ``assertuserfailed`` until it is re-established. A description
    that collides with another item's label is retried once with a qualified
    description. Returns the new QID, or "" once the attempt is given up -- the
    tool is resumable, so a skipped item is created by the next run.
    """
    texts = dict(zip(LANGUAGES, key))
    description = None
    collisions = 0
    for attempt, delay in enumerate((5, 15, 45, 30, 30, 0)):
        data = build_wikibase_content_item_data(
            texts["en"], "", texts,
            **({"description": description} if description else {}),
        )
        try:
            result = client.edit_entity(data, summary=summary)
            return result.get("entity", {}).get("id") or ""
        except WikibaseError as error:
            if attempt == 5:
                print(f"  {key[0][:48]!r}: giving up: {error}", file=sys.stderr, flush=True)
                return ""
            if is_label_conflict(error):
                # Several photographs share an English caption while differing
                # in other languages, so one qualifier is not enough: the second
                # collision needs a description nothing else holds.
                collisions += 1
                suffix = " (image description)" + (
                    f" {collisions}" if collisions > 1 else ""
                )
                description = f"{content_item_description()}{suffix}"
                continue
            if "assertuserfailed" in str(error):
                print("  session expired; signing in again", file=sys.stderr, flush=True)
                try:
                    sign_in(client)
                    continue
                except Exception as login_error:  # noqa: BLE001 - reported, then retried
                    print(f"  sign-in failed: {login_error}", file=sys.stderr, flush=True)
            time.sleep(delay)
    return ""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--apply", action="store_true", help="create items and write bindings")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_REPO_ROOT / ".env")
    parser.add_argument("--api", default=None)
    parser.add_argument("--limit", type=int, default=0, help="stop after N new items")
    parser.add_argument("--pause", type=float, default=0.6)
    parser.add_argument(
        "--summary", default="Image description as an abstract content component"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    labels = load_labels(args.data_dir)
    slots, reasons = collect(args.repo_root)
    known = existing_by_text(labels)

    wanted: dict[tuple[str, ...], list[dict]] = collections.OrderedDict()
    for slot in slots:
        key = tuple(slot["values"][language] for language in LANGUAGES)
        wanted.setdefault(key, []).append(slot)

    unbound = {key: group for key, group in wanted.items() if any(not s["bound"] for s in group)}
    reuse = {key: known[key] for key in unbound if key in known}
    create = [key for key in unbound if key not in known]

    print(f"{len(slots)} bound-able image slot(s) across {len({s['page'] for s in slots})} page(s)")
    for reason, count in reasons.most_common():
        print(f"  skipped: {count} x {reason}")
    print(f"{len(wanted)} distinct description(s); {len(reuse)} reuse an item, {len(create)} need one")

    if not args.apply:
        for key in create[:5]:
            print(f"    new: {key[0][:64]!r}")
        print("\nDry run; pass --apply to create items and write bindings.")
        return 0

    load_env(args.env_file)
    client = WikibaseClient(args.api or os.getenv("WIKIBASE_API", DEFAULT_API), pause=args.pause)
    sign_in(client)

    resolved = dict(reuse)
    created = 0
    failed = 0
    for key in create:
        if args.limit and created >= args.limit:
            break
        qid = create_with_retry(client, key, args.summary)
        if not qid:
            failed += 1
            continue
        resolved[key] = qid
        created += 1
        if created % 25 == 0:
            print(f"  created {created}/{len(create)}", flush=True)

    written = 0
    for key, group in wanted.items():
        qid = resolved.get(key)
        if not qid:
            continue
        for slot in group:
            if slot["bound"]:
                continue
            if write_binding(slot["abstract"], slot["key"], qid):
                written += 1

    print(f"\nCreated {created} content item(s); wrote {written} binding(s).")
    if failed:
        print(
            f"{failed} item(s) could not be created; re-run to retry them.",
            file=sys.stderr,
        )
    print("Now run render_page.py, then verify_content_roundtrip.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
