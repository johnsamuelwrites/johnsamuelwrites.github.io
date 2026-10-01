#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Bring the quotation items in line with Wikibase Cloud's licensing rule.

Wikibase Cloud requires all structured data to be in the public domain or under
CC0. Two kinds of quotation item did not meet that:

Quotations still under copyright (``text_in_wikibase=no`` in ``quotes.csv``)
    become metadata-only items: a descriptive label, ``instance of`` an atomic
    content component, ``creator`` (P15) pointing at the attribution item, and the
    page that publishes the text (P3). Their P40 text, any constructor (P41), and
    the sentence items that held the text in parts are blanked: their labels,
    text, type and ``part of`` link are removed and a description says why. (They
    are blanked rather than deleted so their QIDs never resolve to nothing.) The
    text itself renders from the CSV -- see ``local_text.py``.

Bible verses quoted from the New International Version
    are switched to the public-domain World English Bible, in the labels and P40
    values of their sentence and attribution items.

Every change is computed against the live item, so a re-run only does what is
still outstanding. Nothing is written without ``--apply``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.local_text import QUOTES_CSV, text_in_wikibase
from abstract.normalize_untranslatable_names import sign_in, write_with_retry
from content_update import (
    ABSTRACT_CONTENT_ITEM,
    FAMILIES,
    INSTANCE_OF_PROPERTY,
    MONOLINGUAL_CONTENT_PROPERTY,
    read_rows,
    statement,
)
from languages import ORDER as LANGUAGES
from paths import REPO_ROOT
from wikibase_api import DEFAULT_API, WikibaseClient
from wikibase_write import datavalue, load_env

PART_OF_PROPERTY = "P21"
CONSTRUCTOR_PROPERTY = "P41"
CREATOR_PROPERTY = "P15"
URL_PROPERTY = "P3"
SENTENCE_ITEMTYPE = "Q3836"
QUOTES_PAGE_URL = "https://johnsamuel.info/en/writings/quotes.html"

BLANKED_DESCRIPTION = (
    "unused: this item held part of a quotation still under copyright, "
    "and its text was removed"
)

METADATA_ONLY_DESCRIPTION = (
    "quotation recorded as metadata only; its text is under copyright "
    "and is not stored in this Wikibase"
)

# The author's name is never translated; only the word around it is.
DESCRIPTIVE_LABEL = {
    "en": "Quotation by {name}",
    "fr": "Citation : {name}",
    "es": "Cita: {name}",
    "it": "Citazione: {name}",
    "pt": "Citação: {name}",
    "hi": "उद्धरण: {name}",
    "pa": "ਹਵਾਲਾ: {name}",
    "ml": "ഉദ്ധരണി: {name}",
}

# World English Bible (public domain), split on the sentence items that already
# exist, so each paragraph keeps its P42 ordinals.
PUBLIC_DOMAIN_TEXT = {
    "Q4644": "There is no fear in love;",
    "Q4645": "but perfect love casts out fear, because fear has punishment.",
    "Q4646": "He who fears is not made perfect in love.",
    "Q4647": "But now faith, hope, and love remain—these three.",
    "Q4648": "The greatest of these is love.",
    "Q6330": "1 John 4:18 (World English Bible)",
    "Q6331": "1 Corinthians 13:13 (World English Bible)",
}


def item_ids(claims: dict, prop: str) -> list[str]:
    return [
        claim["mainsnak"]["datavalue"]["value"]["id"]
        for claim in claims.get(prop, [])
        if claim["mainsnak"].get("datavalue")
    ]


def metadata_only_rows() -> list[dict[str, str]]:
    family = FAMILIES["quotes"]
    return [
        row.data
        for row in read_rows(family, QUOTES_CSV)
        if row.data.get("local_qid") and not text_in_wikibase(row.data)
    ]


def metadata_only_edit(entity: dict, row: dict[str, str]) -> dict:
    name = " ".join(row["attribution"].split())
    claims = entity.get("claims", {})
    data: dict = {}
    labels = {
        language: {"language": language, "value": DESCRIPTIVE_LABEL[language].format(name=name)}
        for language in LANGUAGES
        if entity.get("labels", {}).get(language, {}).get("value")
        != DESCRIPTIVE_LABEL[language].format(name=name)
    }
    if labels:
        data["labels"] = labels
    if entity.get("descriptions", {}).get("en", {}).get("value") != METADATA_ONLY_DESCRIPTION:
        data["descriptions"] = {"en": {"language": "en", "value": METADATA_ONLY_DESCRIPTION}}

    changes: list[dict] = []
    for prop in (MONOLINGUAL_CONTENT_PROPERTY, CONSTRUCTOR_PROPERTY):
        changes += [{"id": claim["id"], "remove": ""} for claim in claims.get(prop, [])]
    changes += [
        {"id": claim["id"], "remove": ""}
        for claim in claims.get(INSTANCE_OF_PROPERTY, [])
        if claim["mainsnak"]["datavalue"]["value"]["id"] != ABSTRACT_CONTENT_ITEM
    ]
    if ABSTRACT_CONTENT_ITEM not in item_ids(claims, INSTANCE_OF_PROPERTY):
        changes.append(
            statement(INSTANCE_OF_PROPERTY, "wikibase-item", datavalue(ABSTRACT_CONTENT_ITEM, "wikibase-item"))
        )
    creator = row.get("attribution_qid", "").strip()
    if creator and creator not in item_ids(claims, CREATOR_PROPERTY):
        changes.append(statement(CREATOR_PROPERTY, "wikibase-item", datavalue(creator, "wikibase-item")))
    urls = [claim["mainsnak"]["datavalue"]["value"] for claim in claims.get(URL_PROPERTY, [])]
    if QUOTES_PAGE_URL not in urls:
        changes.append(statement(URL_PROPERTY, "url", datavalue(QUOTES_PAGE_URL, "url")))
    if changes:
        data["claims"] = changes
    return data


def public_domain_edit(entity: dict, text: str) -> dict:
    data: dict = {}
    labels = {
        language: {"language": language, "value": text}
        for language in LANGUAGES
        if entity.get("labels", {}).get(language, {}).get("value") != text
    }
    if labels:
        data["labels"] = labels
    claims = []
    for claim in entity.get("claims", {}).get(MONOLINGUAL_CONTENT_PROPERTY, []):
        value = claim["mainsnak"]["datavalue"]["value"]
        if value.get("language") in LANGUAGES and value.get("text") != text:
            replacement = json.loads(json.dumps(claim))
            replacement["mainsnak"]["datavalue"]["value"]["text"] = text
            claims.append(replacement)
    if claims:
        data["claims"] = claims
    return data


def sentence_parts(client: WikibaseClient, paragraph: str) -> list[str]:
    """Sentence items that hold a paragraph's text, found by their ``part of`` link."""
    payload = client.request({
        "action": "query",
        "list": "search",
        "srsearch": f"haswbstatement:{PART_OF_PROPERTY}={paragraph}",
        "srnamespace": 120,
        "srlimit": "max",
    })
    candidates = [hit["title"].removeprefix("Item:") for hit in payload["query"]["search"]]
    entities = client.entities(candidates) if candidates else {}
    return sorted(
        (
            qid
            for qid, entity in entities.items()
            if "missing" not in entity
            and SENTENCE_ITEMTYPE in item_ids(entity.get("claims", {}), INSTANCE_OF_PROPERTY)
            and paragraph in item_ids(entity.get("claims", {}), PART_OF_PROPERTY)
        ),
        key=lambda qid: int(qid[1:]),
    )


def blank_edit(entity: dict) -> dict:
    """Strip a sentence item down to a description saying why it is empty.

    Its labels and P40 hold the copyrighted text; its type and ``part of`` link
    would keep it attached to the quotation it no longer belongs to.
    """
    data: dict = {}
    labels = {
        language: {"language": language, "remove": ""}
        for language in entity.get("labels", {})
    }
    if labels:
        data["labels"] = labels
    if entity.get("descriptions", {}).get("en", {}).get("value") != BLANKED_DESCRIPTION:
        data["descriptions"] = {
            language: {"language": language, "remove": ""}
            for language in entity.get("descriptions", {})
            if language != "en"
        }
        data["descriptions"]["en"] = {"language": "en", "value": BLANKED_DESCRIPTION}
    claims = [
        {"id": claim["id"], "remove": ""}
        for prop in (MONOLINGUAL_CONTENT_PROPERTY, PART_OF_PROPERTY, INSTANCE_OF_PROPERTY)
        for claim in entity.get("claims", {}).get(prop, [])
    ]
    if claims:
        data["claims"] = claims
    return data


def describe(data: dict) -> str:
    claims = data.get("claims", [])
    removed = sum(1 for claim in claims if "remove" in claim)
    return (
        f"labels={len(data.get('labels', {}))} "
        f"description={'yes' if 'descriptions' in data else 'no'} "
        f"claims: -{removed} +/~{len(claims) - removed}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform writes")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--api", default=None)
    parser.add_argument("--pause", type=float, default=0.6, help="seconds between writes")
    parser.add_argument(
        "--summary",
        default="Quotation licensing: copyrighted text kept out of the Wikibase; Bible verses from the public-domain WEB",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_env(args.env_file)
    client = WikibaseClient(
        args.api or os.getenv("WIKIBASE_API", DEFAULT_API),
        pause=args.pause if args.apply else 0,
    )
    if args.apply:
        sign_in(client)

    rows = metadata_only_rows()
    edits: list[tuple[str, dict]] = []
    blanked: list[str] = []
    live = client.entities([row["local_qid"] for row in rows] + list(PUBLIC_DOMAIN_TEXT))
    for row in rows:
        qid = row["local_qid"]
        data = metadata_only_edit(live[qid], row)
        if data:
            edits.append((qid, data))
        blanked += sentence_parts(client, qid)
    for qid, text in PUBLIC_DOMAIN_TEXT.items():
        data = public_domain_edit(live[qid], text)
        if data:
            edits.append((qid, data))
    if blanked:
        for qid, entity in client.entities(blanked).items():
            data = blank_edit(entity)
            if data:
                edits.append((qid, data))

    for qid, data in edits:
        action = "BLANK" if qid in blanked else "EDIT"
        print(f"{action} {qid}: {describe(data)}")
    print(f"{len(edits)} item edit(s)")
    if not args.apply:
        print("dry run; pass --apply to write")
        return 0

    failed = [qid for qid, data in edits if not write_with_retry(client, qid, data, args.summary)]
    if failed:
        print(f"failed: {', '.join(failed)}; re-run to retry", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
