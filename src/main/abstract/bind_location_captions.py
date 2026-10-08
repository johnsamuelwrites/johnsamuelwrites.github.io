#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Make gallery card captions (``data-location``) Q315 content.

A travel gallery card shows its caption through CSS ``content:
attr(data-location)``. The attribute was written from the English-only
``data_location`` column of the photographies CSV, and ``render_page.py`` did
not own it, so the abstract pages and every non-French language page showed the
English caption ("Door", "Arch", ...).

This tool binds each caption to its content item the way
``bind_image_descriptions.py`` binds ``alt``: the abstract page gets
``data-location="Q..." data-content-data-location="local:Q..."`` and
``render_page.py`` then writes each language's label into the language pages.

A caption is resolved to an existing content item (``Q3185``) by its English
label. A caption with no item yet is reported; with ``--quickstatements`` the
ones that have a row in ``location-caption-translations.csv`` are written as
CREATE blocks, to be imported with ``wikibase_write.py`` before re-running this
tool. Nothing is written to the pages without ``--apply``, and the run is
resumable: an already-bound card is left alone.

``--attribute`` binds the other prose attributes the same way -- an
``aria-label``, ``placeholder`` or ``title`` left as an English literal on an
abstract page -- with their translations in ``interface-label-translations.csv``.
A value that is already a QID is a reference, not prose, and is left alone.
"""

from __future__ import annotations

import argparse
import collections
import csv
import html
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import abstract_index
from abstract.prepare_missing_content import alternate_pages
from abstract.prepare_travel_content import LANGUAGES, monolingual_value, quote
from abstract.render_page import CONTENT_ATTRIBUTE_PREFIX, _base_signature, base_counts

ATTRIBUTE = "data-location"
CONTENT_ITEM_TYPE = "Q3185"
QID_VALUE = re.compile(r"(?:Q[1-9][0-9]*\s*)+")


@dataclass(frozen=True)
class Target:
    """Where an attribute's translations live and how its items are described."""

    translations: Path
    quickstatements: Path
    description: str


CAPTIONS = Target(
    HERE / "location-caption-translations.csv",
    HERE / "location-captions.quickstatements",
    "caption of a photograph in a travel gallery",
)
INTERFACE = Target(
    HERE / "interface-label-translations.csv",
    HERE / "interface-labels.quickstatements",
    "accessible label or hint text of a page control",
)
TARGETS = {
    "data-location": CAPTIONS,
    "aria-label": INTERFACE,
    "placeholder": INTERFACE,
    "title": INTERFACE,
}


def binding(attribute: str) -> str:
    return f"{CONTENT_ATTRIBUTE_PREFIX}{attribute}"


def normalize(value: str) -> str:
    return " ".join(html.unescape(value or "").split())


def caption_key(value: str) -> str:
    """Captions match regardless of case: "Street Light" is "Street light"."""
    return normalize(value).casefold()


@dataclass(frozen=True)
class Caption:
    """One ``data-location`` start tag: where it is and what it says."""

    key: tuple
    start: int
    end: int
    value: str
    bound: str


class Captions(HTMLParser):
    """``signature -> Caption`` for every element carrying the attribute."""

    def __init__(self, text: str, attribute: str = ATTRIBUTE) -> None:
        super().__init__(convert_charrefs=True)
        self.text = text
        self.attribute = attribute
        # HTMLParser counts lines on "\n" alone, so offsets must too.
        self.line_offsets = [0]
        for line in text.split("\n"):
            self.line_offsets.append(self.line_offsets[-1] + len(line) + 1)
        self.counts: collections.Counter = collections.Counter()
        self.found: dict[tuple, Caption] = {}

    def handle_starttag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        index = self.counts[base]
        self.counts[base] += 1
        values = dict(attrs)
        if self.attribute not in values:
            return
        line, column = self.getpos()
        start = self.line_offsets[line - 1] + column
        end = start + len(self.get_starttag_text() or "")
        self.found[(*base, index)] = Caption(
            (*base, index),
            start,
            end,
            normalize(values.get(self.attribute) or ""),
            (values.get(binding(self.attribute)) or "").removeprefix("local:"),
        )

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)


def captions(text: str, attribute: str = ATTRIBUTE) -> dict[tuple, Caption]:
    parser = Captions(text, attribute)
    parser.feed(text)
    parser.close()
    return parser.found


def translated_languages(row: dict[str, str], english: str) -> int:
    """Languages whose label is a translation rather than the English text.

    Some items share an English label but carry it glossed ("Coucher du soleil
    — Sunset") or untranslated; the cleanly translated one is the caption.
    """
    count = 0
    for language in LANGUAGES:
        label = normalize(row.get(language) or "")
        if language != "en" and label and english not in label:
            count += 1
    return count


def content_items_by_english(data_dir: Path, *, untranslated: bool = False) -> dict[str, list[str]]:
    """Content item QIDs keyed by English label, best translated first.

    An item whose labels are all still English would render the English
    caption in every language, so it is left out; ``untranslated=True`` returns
    only those items instead, for their labels to be fixed.
    """
    found: dict[str, list[tuple[int, int, str]]] = collections.defaultdict(list)
    with (data_dir / "labels-wikibase.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if (row.get("itemtype") or "").strip() != CONTENT_ITEM_TYPE:
                continue
            english = normalize(row.get("en") or "")
            if english:
                qid = row["identifier"].strip()
                translated = translated_languages(row, english)
                if (translated == 0) == untranslated:
                    found[caption_key(english)].append((-translated, int(qid[1:]), qid))
    return {english: [qid for *_rank, qid in sorted(ranked)] for english, ranked in found.items()}


def english_values(repo_root: Path, abstract: Path, text: str, attribute: str = ATTRIBUTE) -> dict[tuple, str]:
    """The captions the English page shows, aligned by signature.

    The abstract page was written from the English-only CSV column, so its
    literal is the English caption; the English page is preferred when it is
    structurally aligned, since that is what readers see.
    """
    try:
        english = dict(zip(LANGUAGES, alternate_pages(repo_root, abstract)))["en"]
    except ValueError:
        return {}
    english_text = english.read_text(encoding="utf-8")
    abstract_counts = base_counts(text)
    english_counts = base_counts(english_text)
    return {
        key: caption.value
        for key, caption in captions(english_text, attribute).items()
        if english_counts.get(key[:3]) == abstract_counts.get(key[:3]) and caption.value
    }


def bind_text(text: str, qids: dict[tuple, str], attribute: str = ATTRIBUTE) -> tuple[str, int]:
    """Rewrite the addressed start tags; returns the new text and the count."""
    found = captions(text, attribute)
    value = re.compile(rf'(?<![\w-]){re.escape(attribute)}\s*=\s*"[^"]*"')
    edits = []
    for key, qid in qids.items():
        caption = found.get(key)
        if caption is None or caption.bound:
            continue
        tag = text[caption.start : caption.end]
        rewritten, count = value.subn(
            f'{binding(attribute)}="local:{qid}" {attribute}="{qid}"', tag, count=1
        )
        if count:
            edits.append((caption.start, caption.end, rewritten))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, len(edits)


def plan(
    repo_root: Path, data_dir: Path, attribute: str = ATTRIBUTE
) -> tuple[dict[Path, dict[tuple, str]], dict[str, int], collections.Counter]:
    """Bindings to write per page, unresolved captions and their slot counts."""
    items = content_items_by_english(data_dir)
    bindings: dict[Path, dict[tuple, str]] = {}
    unresolved: collections.Counter = collections.Counter()
    stats: collections.Counter = collections.Counter()
    # Every abstract page, including those whose language pages another
    # generator writes: a literal on the abstract page itself is still a leak.
    pages, _rendered = abstract_index(repo_root)
    for relative in sorted(pages):
        abstract = repo_root / relative
        text = abstract.read_text(encoding="utf-8")
        found = captions(text, attribute)
        if not found:
            continue
        english = english_values(repo_root, abstract, text, attribute)
        for key, caption in found.items():
            if caption.bound:
                stats["already bound"] += 1
                continue
            if QID_VALUE.fullmatch(caption.value):
                stats["reference, not prose"] += 1
                continue
            value = english.get(key) or caption.value
            if not value:
                stats["empty caption"] += 1
                continue
            qids = items.get(caption_key(value))
            if not qids:
                unresolved[value] += 1
                continue
            bindings.setdefault(abstract, {})[key] = qids[0]
            stats["resolved"] += 1
    stats["unresolved"] = sum(unresolved.values())
    return bindings, dict(unresolved), stats


def load_translations(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {
            caption_key(row["en"]): {language: normalize(row.get(language) or "") for language in LANGUAGES}
            for row in csv.DictReader(source)
            if normalize(row.get("en") or "")
        }


def quickstatements(
    captions_needed: list[str],
    translations: dict[str, dict[str, str]],
    untranslated: dict[str, list[str]] | None = None,
    description: str = CAPTIONS.description,
) -> tuple[str, list[str]]:
    """Statements for every caption with a complete translation row.

    A caption whose item exists with English-only labels gets its labels
    translated; any other caption gets a new content item.
    """
    blocks = []
    missing = []
    for caption in sorted(captions_needed):
        texts = translations.get(caption_key(caption))
        if not texts or not all(texts.values()):
            missing.append(caption)
            continue
        existing = (untranslated or {}).get(caption_key(caption))
        if existing:
            blocks.append(
                "\n".join(
                    f'{existing[0]}|L{language}|"{quote(texts[language])}"'
                    for language in LANGUAGES
                    if language != "en"
                )
            )
            continue
        lines = ["CREATE"]
        lines += [f'LAST|L{language}|"{quote(texts[language])}"' for language in LANGUAGES]
        lines += [f"LAST|P40|{monolingual_value(language, texts[language])}" for language in LANGUAGES]
        lines += [f'LAST|Den|"{quote(description)}"', f"LAST|P8|{CONTENT_ITEM_TYPE}"]
        blocks.append("\n".join(lines))
    return ("\n\n".join(blocks) + "\n") if blocks else "", missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--attribute",
        nargs="+",
        choices=sorted(TARGETS),
        default=[ATTRIBUTE],
        help="attributes to bind; those sharing a translation file share one output",
    )
    parser.add_argument("--translations", type=Path)
    parser.add_argument(
        "--quickstatements",
        type=Path,
        nargs="?",
        const=True,
        help="write CREATE blocks for unresolved values that have translations",
    )
    parser.add_argument("--apply", action="store_true", help="write bindings into the abstract pages")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    data_dir = args.data_dir.resolve()

    pending: dict[Target, set[str]] = {}
    for attribute in args.attribute:
        bindings, unresolved, stats = plan(repo_root, data_dir, attribute)
        print(f"== {attribute}")
        for name, count in sorted(stats.items()):
            print(f"{name}: {count}")
        if args.apply:
            written = 0
            for path, qids in sorted(bindings.items()):
                text = path.read_text(encoding="utf-8")
                updated, count = bind_text(text, qids, attribute)
                if count:
                    path.write_text(updated, encoding="utf-8")
                    written += count
            print(f"bound {written} {attribute} values in {len(bindings)} pages")
        if unresolved:
            print(f"{len(unresolved)} {attribute} values have no content item yet")
        pending.setdefault(TARGETS[attribute], set()).update(unresolved)

    if args.quickstatements:
        untranslated = content_items_by_english(data_dir, untranslated=True)
        for target, values in pending.items():
            output_path = target.quickstatements if args.quickstatements is True else args.quickstatements
            output, missing = quickstatements(
                sorted(values),
                load_translations(args.translations or target.translations),
                untranslated,
                target.description,
            )
            if output:
                output_path.write_text(output, encoding="utf-8")
                print(f"wrote {output.count('CREATE')} CREATE blocks and label fixes to {output_path}")
            for value in missing:
                print(f"  no complete translation row: {value!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
