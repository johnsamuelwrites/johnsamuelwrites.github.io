#!/usr/bin/env python3
"""Emit QuickStatements converting 250-char-truncated research/CV Q3185 items
into composed abstract paragraphs (Q3835) built from ordered Q3836 sentences.

The full text of each item lives in its P40 monolingual statements (uncapped),
while its label is capped at 250 characters, so render_page rendered truncated
text. Marking the item as a composed paragraph makes render_page/repair/round-
trip skip it and preserves the full content in the sentence P40 values. Mirrors
the existing compose-long-paragraphs.quickstatements recipe (Q7792/Q7852/Q7853).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from abstract.prepare_abstract_composition import segment
from abstract.prepare_missing_content import content_token
from abstract.prepare_travel_content import LANGUAGES, quote

API = "https://jsamwrites.wikibase.cloud/w/api.php"
COMPOSE_FUNCTION = "Q4182"  # compose ordered paragraph (Q3834)
ITEMS = [
    "Q4045",
    "Q6284",
    "Q7486",
    "Q7602",
    "Q7845",
    "Q7846",
    "Q7855",
    "Q7856",
    "Q7858",
]


def fetch_p40(ids: list[str]) -> dict[str, dict[str, str]]:
    query = urllib.parse.urlencode(
        {"action": "wbgetentities", "ids": "|".join(ids),
         "props": "claims", "format": "json"}
    )
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": "Q315-compose/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        entities = json.load(response)["entities"]
    result: dict[str, dict[str, str]] = {}
    for qid in ids:
        per_language: dict[str, list[str]] = {}
        for claim in entities[qid]["claims"].get("P40", []):
            value = claim["mainsnak"]["datavalue"]["value"]
            per_language.setdefault(value["language"], []).append(value["text"])
        # Where an item carries duplicate P40 for a language (a data artifact on
        # Q7486), the last value is the localized attempt; earlier values repeat
        # the untranslated base. Prefer the last, distinct value.
        result[qid] = {
            language: values[-1] for language, values in per_language.items()
        }
    return result


def sentence_block(token: str, values: tuple[str, ...]) -> list[str]:
    lines = ["CREATE", f'LAST|Len|"{token} abstract sentence"']
    lines += [
        f'LAST|P40|{language}:"{quote(value)}"'
        for language, value in zip(LANGUAGES, values)
        if value
    ]
    lines += [
        'LAST|Den|"language-independent sentence used in an abstract paragraph"',
        "LAST|P8|Q3836",
    ]
    return lines


def main() -> int:
    p40 = fetch_p40(ITEMS)
    out: list[str] = []
    for qid in ITEMS:
        values = tuple(p40[qid].get(language, "") for language in LANGUAGES)
        if not values[0]:
            raise SystemExit(f"{qid} has no English P40")
        segments = segment(values)
        out.append(f"{qid}|P8|Q3835")
        out.append("")
        out.append(f"{qid}|P41|{COMPOSE_FUNCTION}")
        out.append("")
        for ordinal, sentence in enumerate(segments, 1):
            token = content_token(sentence)
            block = sentence_block(token, sentence)
            block.append(f'LAST|P21|{qid}|P42|"{ordinal}"')
            out.extend(block)
            out.append("")
    Path("src/main/abstract/compose-research-paragraphs.quickstatements").write_text(
        "\n".join(out).rstrip() + "\n", encoding="utf-8"
    )
    counts = {qid: len(segment(tuple(p40[qid].get(l, "") for l in LANGUAGES)))
              for qid in ITEMS}
    print("segments per item:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
