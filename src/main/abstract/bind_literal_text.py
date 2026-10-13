#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Bind literal text left in an abstract page to content items.

``verify_abstract_literals.py`` finds natural-language text on Q315 pages. Where
the language pages already translate it -- and stay structurally aligned with
the abstract page -- the translations exist; they are only not owned by Q315.
This tool makes them content:

1. every element of the page whose whole text is a literal is a slot;
2. each language's value is read from the aligned language page (same
   ``(tag, class, role, occurrence)`` signature, same signature count), and the
   most frequent value per English text wins, so one English line gets one item;
3. a slot whose English text already has a translated content item is bound
   to it; the others are written to a review CSV and, with ``--quickstatements``,
   as CREATE blocks for ``wikibase_write.py``;
4. ``--apply`` writes ``data-content="local:Q..."`` and shows the QID, as every
   bound text slot does; ``render_page.py`` then writes each language's label.

A slot is skipped, never guessed, when a language page is misaligned for its
signature or shows no text there. Re-run after the import to bind the rest.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from abstract.bind_location_captions import (
    caption_key,
    content_items_by_english,
    normalize,
    quickstatements,
)
from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import abstract_index
from abstract.prepare_missing_content import alternate_pages
from abstract.prepare_travel_content import LANGUAGES
from abstract.render_page import TEXT_TAGS, _base_signature, base_counts
from abstract.verify_abstract_literals import ENDONYMS, SKIPPED, VOID, is_literal

DESCRIPTION = "language-independent content component used by an abstract page"


@dataclass
class Slot:
    key: tuple
    inner_start: int
    inner_end: int
    text: str
    bound: bool
    # Inside an element marked as not Q315 content (`lang`, `translate="no"`).
    exempt: bool = False


class Slots(HTMLParser):
    """Every element's direct text, with offsets of its content."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = text
        self.offsets = [0]
        for line in text.split("\n"):
            self.offsets.append(self.offsets[-1] + len(line) + 1)
        self.counts: collections.Counter = collections.Counter()
        self.stack: list[list] = []
        self.slots: dict[tuple, Slot] = {}

    def _at(self) -> int:
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        key = (*base, self.counts[base])
        self.counts[base] += 1
        if self.stack:
            self.stack[-1][3] = True  # the parent has an element child
        if tag in VOID:
            return
        start = self._at() + len(self.get_starttag_text() or "")
        values = dict(attrs)
        bound = "data-content" in values or "data-entity" in values
        language = (values.get("lang") or "").strip()
        exempt = (bool(self.stack) and self.stack[-1][5]) or values.get("translate") == "no" or (
            bool(language) and language != "zxx"
        )
        self.stack.append([tag, key, start, False, bound, exempt])

    def handle_startendtag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        self.counts[base] += 1
        if self.stack:
            self.stack[-1][3] = True

    def handle_endtag(self, tag) -> None:
        if not any(frame[0] == tag for frame in self.stack):
            return
        end = self._at()
        while self.stack:
            name, key, start, had_child, bound, exempt = self.stack.pop()
            if name == tag:
                inside = {frame[0] for frame in self.stack} | {name}
                if not had_child and not SKIPPED.intersection(inside):
                    text = normalize(self.source[start:end])
                    self.slots[key] = Slot(key, start, end, text, bound, exempt)
                return
            if self.stack:
                self.stack[-1][3] = True


def slots(text: str) -> dict[tuple, Slot]:
    parser = Slots(text)
    parser.feed(text)
    parser.close()
    return parser.slots


def literal_slots(text: str) -> dict[tuple, Slot]:
    return {
        key: slot
        for key, slot in slots(text).items()
        if not slot.bound
        and not slot.exempt
        # Only tags the renderer writes: a binding it cannot place never renders.
        and key[0] in TEXT_TAGS
        and is_literal(slot.text)
        and slot.text not in ENDONYMS
    }


def collect(repo_root: Path, abstract: Path) -> tuple[dict[tuple, dict[str, str]], collections.Counter]:
    """``slot key -> {language: value}`` for every alignable literal slot."""
    text = abstract.read_text(encoding="utf-8")
    wanted = literal_slots(text)
    reasons: collections.Counter = collections.Counter()
    if not wanted:
        return {}, reasons
    pages = dict(zip(LANGUAGES, alternate_pages(repo_root, abstract)))
    counts = base_counts(text)
    per_language = {}
    for language, page in pages.items():
        page_text = page.read_text(encoding="utf-8")
        per_language[language] = (base_counts(page_text), slots(page_text))
    found: dict[tuple, dict[str, str]] = {}
    for key in wanted:
        values = {}
        for language, (page_counts, page_slots) in per_language.items():
            slot = page_slots.get(key)
            if page_counts.get(key[:3]) != counts.get(key[:3]) or slot is None or not slot.text:
                break
            values[language] = slot.text
        else:
            found[key] = values
            continue
        reasons[f"{language} page misaligned or empty"] += 1
    return found, reasons


def majority(found: dict[tuple, dict[str, str]]) -> dict[str, dict[str, str]]:
    """One translation per English text: the most frequent value per language."""
    tallies: dict[str, dict[str, collections.Counter]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter)
    )
    for values in found.values():
        for language, value in values.items():
            tallies[values["en"]][language][value] += 1
    return {
        english: {language: tally.most_common(1)[0][0] for language, tally in by_language.items()}
        for english, by_language in tallies.items()
    }


def bind_text(text: str, qids: dict[tuple, str]) -> tuple[str, int]:
    """Bind the addressed slots: add ``data-content`` and show the QID."""
    current = slots(text)
    edits = []
    for key, qid in qids.items():
        slot = current.get(key)
        if slot is None or slot.bound:
            continue
        tag_end = slot.inner_start
        tag_start = text.rfind("<", 0, tag_end)
        start_tag = text[tag_start:tag_end]
        closing = "/>" if start_tag.endswith("/>") else ">"
        start_tag = f'{start_tag[: -len(closing)].rstrip()} data-content="local:{qid}"{closing}'
        inner = text[slot.inner_start : slot.inner_end]
        leading = inner[: len(inner) - len(inner.lstrip())]
        trailing = inner[len(inner.rstrip()) :]
        edits.append((tag_start, slot.inner_end, f"{start_tag}{leading}{qid}{trailing}"))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, len(edits)


def page_path(repo_root: Path, qid: str) -> Path:
    pages, _ = abstract_index(repo_root)
    for relative, metadata in pages.items():
        if metadata.qid == qid:
            return repo_root / relative
    raise SystemExit(f"no abstract page declares {qid}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--page", required=True, help="abstract page QID, e.g. Q7946")
    parser.add_argument("--translations", type=Path, help="write the review CSV here")
    parser.add_argument(
        "--reviewed",
        type=Path,
        help="reviewed CSV (en,fr,...) whose rows replace the pages' translations",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        metavar="SHOWN=CANONICAL",
        help="bind slots whose English page shows SHOWN to CANONICAL's item, "
        "for an English page that carries another language's text",
    )
    parser.add_argument("--quickstatements", type=Path, help="write CREATE blocks here")
    parser.add_argument("--apply", action="store_true", help="bind slots that have items")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    abstract = page_path(repo_root, args.page)

    found, reasons = collect(repo_root, abstract)
    aliases = dict(alias.split("=", 1) for alias in args.alias)
    for values in found.values():
        values["en"] = aliases.get(values["en"], values["en"])
    texts = majority(found)
    if args.reviewed:
        with args.reviewed.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("en") in texts:
                    texts[row["en"]] = {language: normalize(row[language]) for language in LANGUAGES}
    items = content_items_by_english(args.data_dir.resolve())
    qids = {
        key: items[caption_key(values["en"])][0]
        for key, values in found.items()
        if caption_key(values["en"]) in items
    }
    missing = sorted({values["en"] for key, values in found.items() if key not in qids})
    print(f"{abstract.relative_to(repo_root)}: {len(found)} alignable literal slot(s), "
          f"{len(texts)} distinct text(s); {len(qids)} slot(s) have an item, "
          f"{len(missing)} text(s) need one")
    for reason, count in reasons.items():
        print(f"  skipped {count}: {reason}")

    if args.translations:
        with args.translations.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(LANGUAGES))
            writer.writeheader()
            for english in missing:
                writer.writerow(texts[english])
        print(f"wrote {len(missing)} row(s) to {args.translations}")
    if args.quickstatements and missing:
        output, incomplete = quickstatements(
            missing,
            {caption_key(english): texts[english] for english in missing},
            content_items_by_english(args.data_dir.resolve(), untranslated=True),
            DESCRIPTION,
        )
        args.quickstatements.write_text(output, encoding="utf-8")
        print(f"wrote {output.count('CREATE')} CREATE block(s) to {args.quickstatements}")
        for english in incomplete:
            print(f"  incomplete translations: {english!r}", file=sys.stderr)
    if args.apply:
        updated, count = bind_text(abstract.read_text(encoding="utf-8"), qids)
        abstract.write_text(updated, encoding="utf-8")
        print(f"bound {count} slot(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
