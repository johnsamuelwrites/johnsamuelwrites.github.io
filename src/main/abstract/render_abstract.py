#!/usr/bin/env python3
"""Render composed abstract paragraphs into their concrete language pages.

The renderer is driven by the repository, not by a hard-coded page: it
discovers abstract pages and their language targets from the migration
registry, finds every ``<q-call>``-composed paragraph inside each abstract
page, resolves it from a pinned per-page Wikibase snapshot, evaluates the
QID-addressed function, and writes the realized text into each language page.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.functions.registry import FunctionRegistry
from abstract.functions.text import (
    compose_ordered_paragraph,
    concatenate_monolingual_text,
)
from abstract.prepare_travel_content import LANGUAGES
from abstract.wikibase_resolver import WikibaseResolver

DEFAULT_SNAPSHOTS = HERE / "snapshots"
DEFAULT_IMPLEMENTATIONS = HERE / "function-implementations.json"


@dataclass(frozen=True)
class ComposedParagraph:
    """An element whose text is produced by a ``<q-call>`` composition."""

    item: str
    tag: str
    css_class: str


class ParagraphFinder(HTMLParser):
    """Locate elements that wrap a ``<q-call>`` and carry ``data-content``."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict[str, str]] = []
        self.found: dict[str, ComposedParagraph] = {}

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if tag == "q-call":
            for frame in reversed(self.stack):
                if frame["item"]:
                    self.found.setdefault(
                        frame["item"],
                        ComposedParagraph(
                            frame["item"], frame["tag"], frame["class"]
                        ),
                    )
                    break
        content = values.get("data-content") or ""
        item = content.removeprefix("local:") if content.startswith("local:") else ""
        self.stack.append(
            {"tag": tag, "item": item, "class": values.get("class") or ""}
        )

    def handle_endtag(self, tag) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break


def composed_paragraphs(path: Path) -> list[ComposedParagraph]:
    finder = ParagraphFinder()
    finder.feed(path.read_text(encoding="utf-8"))
    return list(finder.found.values())


def registry(path: Path) -> FunctionRegistry:
    mappings = json.loads(path.read_text(encoding="utf-8"))
    builtins = {
        "concatenate_monolingual_text": concatenate_monolingual_text,
        "compose_ordered_paragraph": compose_ordered_paragraph,
    }
    result = FunctionRegistry()
    for qid, implementation in mappings.items():
        if implementation not in builtins:
            raise ValueError(f"unknown function implementation {implementation}")
        result.register(qid, builtins[implementation])
    return result


def paragraph_markup(
    paragraph: ComposedParagraph, text: str, function: str, indent: str
) -> str:
    return (
        f'{indent}<{paragraph.tag} class="{paragraph.css_class}" '
        f'data-q315-source="local:{paragraph.item}" '
        f'data-q315-function="local:{function}">'
        f"{html.escape(text)}</{paragraph.tag}>"
    )


def _locator(paragraph: ComposedParagraph) -> re.Pattern[str]:
    tag = re.escape(paragraph.tag)
    marker = rf'data-q315-source="local:{paragraph.item}"'
    css = rf'class="{re.escape(paragraph.css_class)}"'
    return re.compile(
        rf"(?P<indent>^[ \t]*)<{tag}\b[^>]*(?:{marker}|{css})[^>]*>.*?</{tag}>",
        flags=re.MULTILINE | re.DOTALL,
    )


def update_page(
    source: str, paragraph: ComposedParagraph, text: str, function: str
) -> str:
    locator = _locator(paragraph)
    matches = locator.findall(source)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one '{paragraph.css_class}' "
            f"{paragraph.tag} for {paragraph.item}, found {len(matches)}"
        )
    match = locator.search(source)
    return locator.sub(
        paragraph_markup(paragraph, text, function, match.group("indent")),
        source,
        count=1,
    )


def render(
    repo_root: Path,
    snapshots: Path,
    implementations: Path,
    page: str,
    check: bool,
) -> int:
    runtime = registry(implementations)
    rows = [
        row
        for row in discover(repo_root)
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not rows:
        raise ValueError(f"no abstract page declares QID {page}")

    rendered_pages = 0
    changed: list[str] = []
    for row in sorted(rows, key=lambda row: row["page_qid"]):
        paragraphs = composed_paragraphs(repo_root / row["abstract_path"])
        if not paragraphs:
            continue
        snapshot = snapshots / f"{row['page_qid']}.json"
        if not snapshot.is_file():
            if page:
                raise ValueError(f"missing snapshot {snapshot}")
            print(f"SKIP {row['page_qid']}: no snapshot at {snapshot}")
            continue
        resolver = WikibaseResolver.from_path(snapshot)
        targets = [
            (language, row[f"target_{language}"])
            for language in LANGUAGES
            if row[f"target_{language}"]
        ]
        for paragraph in paragraphs:
            resolved = resolver.paragraph(paragraph.item)
            for language, relative in targets:
                path = repo_root / relative
                source = path.read_text(encoding="utf-8")
                value = runtime.evaluate(resolver.call(resolved, language))
                updated = update_page(
                    source, paragraph, value.text, resolved.function
                )
                if updated != source:
                    changed.append(relative)
                    if not check:
                        path.write_text(updated, encoding="utf-8")
        rendered_pages += 1

    if check and changed:
        for relative in changed:
            print(f"STALE: {relative}")
        return 1
    action = "Validated" if check else "Rendered"
    print(f"{action} composed paragraphs for {rendered_pages} abstract page(s)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument(
        "--implementations", type=Path, default=DEFAULT_IMPLEMENTATIONS
    )
    parser.add_argument(
        "--page", default="", help="restrict rendering to a single page QID"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return render(
        args.repo_root.resolve(),
        args.snapshots,
        args.implementations,
        args.page,
        args.check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
