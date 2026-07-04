#!/usr/bin/env python3
"""Render canonical Q315 label text into the bound slots of language pages.

Unlike ``render_abstract.py`` (which realizes ``<q-call>``-composed paragraphs),
this renderer rewrites the *atomic* ``data-content``/``data-entity`` text slots in
place: each bound element's text node is replaced with the entity's Wikibase label
for the target language, read from ``labels-wikibase.csv``. The legacy page's
chrome, navigation and asset links are left untouched -- only bound text nodes
change -- and a ``Q315 renderer`` generator meta is injected so the page's
migration ownership flips from ``legacy`` to ``abstract``.

The mapping between an abstract-page binding and a language-page slot is the
stable ``(tag, class, role, occurrence)`` signature shared by ``DirectTextSlots``
in ``prepare_travel_content`` (and therefore by ``verify_content_roundtrip``): the
label that the round-trip expects is written into the slot that carries the same
signature. Slots whose signature is absent from a legacy page, or that wrap child
elements, are left alone and reported so they can be reconciled structurally.
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_travel_content import LANGUAGES, TEXT_TAGS

DEFAULT_DATA = DEFAULT_REPO_ROOT.parent / "Q42761025" / "data"

# Function-composed results (abstract paragraphs/sentences) are realized by
# render_abstract.py from a pinned snapshot, not by substituting the label of the
# result entity. They are excluded here by item type rather than by hard-coded QID.
COMPOSED_ITEMTYPES = frozenset({"Q3835", "Q3836"})

GENERATOR_META = '<meta name="generator" content="Q315 renderer" />'

Signature = tuple[str, str, str, int]


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with (data_dir / "labels-wikibase.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            result[row["identifier"]] = row
    return result


def _base_signature(tag: str, attrs: list[tuple[str, str | None]]) -> tuple[str, str, str]:
    values = dict(attrs)
    return (
        tag,
        ".".join(sorted((values.get("class") or "").split())),
        values.get("role") or "",
    )


class TemplateBindings(HTMLParser):
    """Collect ``signature -> qid`` for every bound atomic slot in a template.

    Occurrence counting mirrors ``DirectTextSlots`` exactly so the produced
    signatures address the same slots that ``slots()`` reads from a language page.
    """

    def __init__(self) -> None:
        super().__init__()
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.bindings: dict[Signature, str] = {}

    def handle_starttag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        index = self.counts[base]
        self.counts[base] += 1
        key = (*base, index)
        values = dict(attrs)
        for attr in ("data-content", "data-entity"):
            value = values.get(attr) or ""
            if value.startswith("local:"):
                self.bindings[key] = value.removeprefix("local:")


def template_bindings(path: Path) -> dict[Signature, str]:
    parser = TemplateBindings()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.bindings


@dataclass
class _Frame:
    tag: str
    key: Signature
    inner_start: int
    had_child: bool = False


class SlotRewriter(HTMLParser):
    """Replace the direct text of bound, pure-text slots in a language page.

    Rewrites are driven off the original source by character offset so scripts,
    styles, entities and every unbound byte pass through unchanged.
    """

    def __init__(self, source: str, targets: dict[Signature, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.targets = targets
        self._line_starts = self._compute_line_starts(source)
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.stack: list[_Frame] = []
        self.regions: list[tuple[int, int, str]] = []
        self.applied: set[Signature] = set()
        self.rewritten: set[Signature] = set()
        self.structural: set[Signature] = set()

    @staticmethod
    def _compute_line_starts(source: str) -> list[int]:
        starts = [0]
        for index, character in enumerate(source):
            if character == "\n":
                starts.append(index + 1)
        return starts

    def _absolute(self, pos: tuple[int, int]) -> int:
        line, column = pos
        return self._line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs) -> None:
        base = _base_signature(tag, attrs)
        index = self.counts[base]
        self.counts[base] += 1
        key = (*base, index)
        if self.stack:
            self.stack[-1].had_child = True
        start = self._absolute(self.getpos())
        inner_start = start + len(self.get_starttag_text() or "")
        self.stack.append(_Frame(tag, key, inner_start))

    def handle_startendtag(self, tag, attrs) -> None:
        # A void element (<img/>, <br/>) consumes an occurrence index but has no
        # inner text slot; mark the parent as having a child so it is never
        # treated as a pure-text slot.
        base = _base_signature(tag, attrs)
        self.counts[base] += 1
        if self.stack:
            self.stack[-1].had_child = True

    def handle_endtag(self, tag) -> None:
        if tag not in (frame.tag for frame in self.stack):
            return
        end = self._absolute(self.getpos())
        while self.stack:
            frame = self.stack.pop()
            if frame.tag == tag:
                self._finalize(frame, end)
                break
            # Improperly nested: an ancestor's end tag closed this frame. It is
            # not a clean text slot, so do not rewrite it.
            if frame.key in self.targets:
                self.structural.add(frame.key)

    def _finalize(self, frame: _Frame, end: int) -> None:
        if frame.key not in self.targets:
            return
        if frame.had_child or frame.tag not in TEXT_TAGS:
            self.structural.add(frame.key)
            return
        target = self.targets[frame.key]
        current = " ".join(html.unescape(self.source[frame.inner_start : end]).split())
        self.applied.add(frame.key)
        if current != target:
            self.regions.append((frame.inner_start, end, target))
            self.rewritten.add(frame.key)

    def rewrite(self) -> str:
        self.feed(self.source)
        self.close()
        result = self.source
        for start, end, text in sorted(self.regions, reverse=True):
            result = result[:start] + html.escape(text, quote=False) + result[end:]
        return result

    @property
    def absent(self) -> set[Signature]:
        return set(self.targets) - self.applied - self.structural


def inject_generator_meta(text: str) -> str:
    """Add the Q315-renderer generator meta once, right after ``<head>``."""
    if 'name="generator" content="Q315 renderer"' in text:
        return text
    marker = "<head>"
    index = text.find(marker)
    if index == -1:
        return text
    insert_at = index + len(marker)
    return f"{text[:insert_at]}\n        {GENERATOR_META}{text[insert_at:]}"


def render(
    repo_root: Path,
    data_dir: Path,
    page: str,
    check: bool,
) -> int:
    labels = load_labels(data_dir)
    rows = [
        row
        for row in discover(repo_root)
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not rows:
        raise ValueError(f"no abstract page declares QID {page}")

    changed: list[str] = []
    rewritten_slots = 0
    structural: list[tuple[str, str, str]] = []
    skipped_pages = 0
    for row in sorted(rows, key=lambda row: row["page_qid"]):
        abstract = repo_root / row["abstract_path"]
        atomic = {
            key: qid
            for key, qid in template_bindings(abstract).items()
            if labels.get(qid, {}).get("itemtype", "").strip() not in COMPOSED_ITEMTYPES
        }
        targets = [
            (language, row[f"target_{language}"])
            for language in LANGUAGES
            if row[f"target_{language}"]
        ]
        missing = sorted(
            {
                qid
                for qid in atomic.values()
                for language, _ in targets
                if not labels.get(qid, {}).get(language, "").strip()
            },
            key=lambda value: int(value[1:]),
        )
        if missing:
            skipped_pages += 1
            preview = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
            print(f"SKIP {row['page_qid']}: missing labels for {preview}")
            continue
        for language, relative in targets:
            path = repo_root / relative
            source = path.read_text(encoding="utf-8")
            replacements = {
                key: labels[qid][language].strip() for key, qid in atomic.items()
            }
            rewriter = SlotRewriter(source, replacements)
            updated = inject_generator_meta(rewriter.rewrite())
            for key in sorted(rewriter.absent):
                structural.append((row["page_qid"], language, f"{key} -> {atomic[key]}"))
            if updated != source:
                changed.append(relative)
                rewritten_slots += len(rewriter.rewritten)
                if not check:
                    path.write_text(updated, encoding="utf-8")

    if check and changed:
        for relative in changed:
            print(f"STALE: {relative}")
    for page_qid, language, detail in structural:
        print(f"UNPLACED {page_qid} [{language}]: {detail}")
    action = "Would render" if check else "Rendered"
    print(
        f"{action} {len(changed)} language page(s); "
        f"{rewritten_slots} slot text rewrites; "
        f"{skipped_pages} page(s) skipped for missing labels; "
        f"{len(structural)} unplaced slot(s)"
    )
    return 1 if (check and changed) else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--page", default="", help="restrict rendering to a single abstract page QID"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the pages that would change without writing them",
    )
    args = parser.parse_args(argv)
    try:
        return render(
            args.repo_root.resolve(),
            args.data_dir.resolve(),
            args.page,
            args.check,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
