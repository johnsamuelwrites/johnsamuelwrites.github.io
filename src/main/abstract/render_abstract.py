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
from abstract.repair_structure import Tree, _walk
from abstract.wikibase_resolver import WikibaseResolver

DEFAULT_SNAPSHOTS = HERE / "snapshots"
DEFAULT_IMPLEMENTATIONS = HERE / "function-implementations.json"


@dataclass(frozen=True)
class ComposedParagraph:
    """An element whose text is produced by a ``<q-call>`` composition."""

    item: str
    tag: str
    css_class: str
    parent_tag: str = ""
    parent_class: str = ""


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
                    parent = next(
                        (
                            candidate
                            for candidate in reversed(self.stack)
                            if candidate is not frame
                        ),
                        {"tag": "", "class": ""},
                    )
                    self.found.setdefault(
                        frame["item"],
                        ComposedParagraph(
                            frame["item"],
                            frame["tag"],
                            frame["class"],
                            parent["tag"],
                            ".".join(sorted(parent["class"].split())),
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
    class_attr = (
        f' class="{paragraph.css_class}"' if paragraph.css_class else ""
    )
    return (
        f'{indent}<{paragraph.tag}{class_attr} '
        f'data-q315-source="local:{paragraph.item}" '
        f'data-q315-function="local:{function}">'
        f"{html.escape(text)}</{paragraph.tag}>"
    )


def _normalized_text(value: str) -> str:
    visible = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", html.unescape(visible)).strip()


def _structured_markup(
    paragraph: ComposedParagraph,
    body: str,
    text: str,
    function: str,
    indent: str,
) -> str:
    """Render text while retaining inline title/link elements from a legacy slot.

    Research citations store their translatable suffix in P40 and retain a
    language-independent ``<b>`` title before it. Link positions are represented
    by ``()`` in P40. Preserve those nodes and place each anchor back into the
    corresponding parentheses instead of flattening the paragraph.
    """
    prefix = ""
    remainder = body
    prefix_match = re.match(
        r"(?P<space>\s*)(?P<prefix>(?:<(?:b|strong)\b[^>]*>.*?</(?:b|strong)>\s*)+)",
        remainder,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if prefix_match:
        prefix = prefix_match.group("prefix").strip()
        remainder = remainder[prefix_match.end():]
    anchors = re.findall(r"<a\b[^>]*>.*?</a>", remainder, re.DOTALL | re.IGNORECASE)
    rendered = html.escape(text)
    for anchor in anchors:
        if "()" not in rendered:
            break
        rendered = rendered.replace("()", f"({anchor})", 1)
    parts = [part for part in (prefix, rendered) if part]
    attrs = (
        f'class="{paragraph.css_class}" ' if paragraph.css_class else ""
    )
    return (
        f"{indent}<{paragraph.tag} {attrs}"
        f'data-q315-source="local:{paragraph.item}" '
        f'data-q315-function="local:{function}">'
        f"{''.join(parts)}</{paragraph.tag}>"
    )


def _locator(paragraph: ComposedParagraph) -> re.Pattern[str]:
    tag = re.escape(paragraph.tag)
    marker = rf'data-q315-source="local:{paragraph.item}"'
    css = rf'class="{re.escape(paragraph.css_class)}"'
    return re.compile(
        rf"(?P<indent>^[ \t]*)<{tag}\b[^>]*(?:{marker}|{css})[^>]*>"
        rf"(?P<body>.*?)</{tag}>",
        flags=re.MULTILINE | re.DOTALL,
    )


def update_page(
    source: str,
    paragraph: ComposedParagraph,
    text: str,
    function: str,
    previous_values: Sequence[str] = (),
    occurrence_hint: int | None = None,
) -> str:
    locator = _locator(paragraph)
    # A rendered marker identifies the paragraph more precisely than a shared
    # CSS class (for example ten research cards all use
    # ``research-description``). Prefer it before the class-based locator.
    tag = re.escape(paragraph.tag)
    marker_locator = re.compile(
        rf"(?P<indent>^[ \t]*)<{tag}\b[^>]*"
        rf'data-q315-source="local:{paragraph.item}"[^>]*>'
        rf"(?P<body>.*?)</{tag}>",
        flags=re.MULTILINE | re.DOTALL,
    )
    marker_matches = marker_locator.findall(source)
    matches = locator.findall(source)
    if len(marker_matches) == 1:
        locator = marker_locator
        match = locator.search(source)
    elif len(matches) == 1:
        match = locator.search(source)
    else:
        candidates = {
            re.sub(r"\s+", " ", value).strip()
            for value in previous_values
            if value
        }
        fallback = re.compile(
            rf"(?P<indent>^[ \t]*)<{tag}\b[^>]*>(?P<body>.*?)</{tag}>",
            flags=re.MULTILINE | re.DOTALL,
        )
        text_matches = []
        structured_matches = []
        for candidate in fallback.finditer(source):
            visible = _normalized_text(candidate.group("body"))
            if visible in candidates:
                text_matches.append(candidate)
                continue
            without_inline = re.sub(
                r"<(?:a|b|strong)\b[^>]*>.*?</(?:a|b|strong)>",
                "",
                candidate.group("body"),
                flags=re.DOTALL | re.IGNORECASE,
            )
            if _normalized_text(without_inline) in candidates:
                structured_matches.append(candidate)
        if len(text_matches) == 1:
            match = text_matches[0]
            locator = re.compile(re.escape(match.group(0)))
        elif len(structured_matches) == 1:
            match = structured_matches[0]
            return source[:match.start()] + _structured_markup(
                paragraph,
                match.group("body"),
                text,
                function,
                match.group("indent"),
            ) + source[match.end():]
        else:
            tree = Tree(source)
            same_signature = [
                node
                for node in _walk(tree.root)
                if node.tag == paragraph.tag
                and node.cls == ".".join(sorted(paragraph.css_class.split()))
                and node.close_start is not None
            ]
            if occurrence_hint is not None and occurrence_hint < len(same_signature):
                node = same_signature[occurrence_hint]
                end = node.close_start + len(node.tag) + 3
                body = source[node.open_end:node.close_start]
                replacement = _structured_markup(
                    paragraph,
                    body,
                    text,
                    function,
                    tree.line_indent(node.open_start),
                )
                return source[:node.open_start] + replacement + source[end:]
            context_nodes = [
                node
                for node in _walk(tree.root)
                if node.tag == paragraph.tag
                and node.cls == ".".join(sorted(paragraph.css_class.split()))
                and node.parent is not None
                and node.parent.tag == paragraph.parent_tag
                and node.parent.cls == paragraph.parent_class
                and node.close_start is not None
            ]
            if len(context_nodes) == 1:
                node = context_nodes[0]
                end = node.close_start + len(node.tag) + 3
                body = source[node.open_end:node.close_start]
                replacement = _structured_markup(
                    paragraph,
                    body,
                    text,
                    function,
                    tree.line_indent(node.open_start),
                )
                return source[:node.open_start] + replacement + source[end:]
            raise ValueError(
                f"expected exactly one '{paragraph.css_class}' "
                f"{paragraph.tag} for {paragraph.item}, found {len(matches)} "
                f"by marker/class, {len(text_matches)} by previous text, and "
                f"{len(structured_matches)} by structured text"
            )
    if match is None:
        raise ValueError(
            f"expected exactly one '{paragraph.css_class}' "
            f"{paragraph.tag} for {paragraph.item}, found {len(matches)}"
        )
    body = match.groupdict().get("body", "")
    replacement = (
        _structured_markup(
            paragraph, body, text, function, match.group("indent")
        )
        if re.search(r"<(?:a|b|strong)\b", body, re.IGNORECASE)
        else paragraph_markup(paragraph, text, function, match.group("indent"))
    )
    return locator.sub(replacement, source, count=1)


def render(
    repo_root: Path,
    snapshots: Path,
    implementations: Path,
    page: str,
    check: bool,
    items: frozenset[str] = frozenset(),
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
    errors: list[str] = []
    for row in sorted(rows, key=lambda row: row["page_qid"]):
        paragraphs = composed_paragraphs(repo_root / row["abstract_path"])
        if items:
            paragraphs = [
                paragraph for paragraph in paragraphs if paragraph.item in items
            ]
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
            try:
                resolved = resolver.paragraph(paragraph.item)
            except (ValueError, KeyError) as error:
                errors.append(f"{row['page_qid']} {paragraph.item}: {error}")
                continue
            occurrence_hint: int | None = None
            for language, relative in targets:
                path = repo_root / relative
                source = path.read_text(encoding="utf-8")
                try:
                    value = runtime.evaluate(resolver.call(resolved, language))
                except (ValueError, KeyError) as error:
                    errors.append(f"{relative} ({language}) {paragraph.item}: {error}")
                    continue
                entity = resolver.entities[paragraph.item]
                previous_values = [
                    entity.get("labels", {}).get(language, {}).get("value", "")
                ]
                previous_values.extend(
                    statement["mainsnak"]["datavalue"]["value"]["text"]
                    for statement in entity["claims"].get("P40", [])
                    if statement["mainsnak"]["datavalue"]["value"]["language"]
                    == language
                )
                try:
                    updated = update_page(
                        source,
                        paragraph,
                        value.text,
                        resolved.function,
                        previous_values,
                        occurrence_hint,
                    )
                except ValueError as error:
                    # A single page that cannot be located must not abort the
                    # whole batch: record it and keep rendering the rest, so one
                    # un-migrated legacy page does not block every composed
                    # paragraph across the site.
                    errors.append(f"{relative} ({language}): {error}")
                    continue
                if updated != source:
                    changed.append(relative)
                    if not check:
                        path.write_text(updated, encoding="utf-8")
                if language == "en":
                    tree = Tree(updated)
                    same_signature = [
                        node
                        for node in _walk(tree.root)
                        if node.tag == paragraph.tag
                        and node.cls == ".".join(
                            sorted(paragraph.css_class.split())
                        )
                    ]
                    occurrence_hint = next(
                        (
                            index
                            for index, node in enumerate(same_signature)
                            if f'data-q315-source="local:{paragraph.item}"'
                            in updated[node.open_start:node.open_end]
                        ),
                        None,
                    )
        rendered_pages += 1

    for message in errors:
        print(f"UNPLACED {message}", file=sys.stderr)
    if check and changed:
        for relative in changed:
            print(f"STALE: {relative}")
    action = "Validated" if check else "Rendered"
    print(
        f"{action} composed paragraphs for {rendered_pages} abstract page(s); "
        f"{len(errors)} paragraph(s) could not be placed"
    )
    return 1 if (errors or (check and changed)) else 0


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
    parser.add_argument(
        "--item",
        action="append",
        default=[],
        help="restrict rendering to a composed paragraph QID (repeatable)",
    )
    args = parser.parse_args(argv)
    return render(
        args.repo_root.resolve(),
        args.snapshots,
        args.implementations,
        args.page,
        args.check,
        frozenset(args.item),
    )


if __name__ == "__main__":
    raise SystemExit(main())
