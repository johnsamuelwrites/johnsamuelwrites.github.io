#!/usr/bin/env python3
"""Render the Q3062 hero paragraph into all eight concrete language pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_MANIFEST, DEFAULT_REPO_ROOT, load_groups
from abstract.functions.registry import FunctionRegistry
from abstract.functions.text import concatenate_monolingual_text
from abstract.wikibase_resolver import WikibaseResolver


DEFAULT_SNAPSHOT = HERE / "snapshots" / "Q3062-hero.json"
DEFAULT_IMPLEMENTATIONS = HERE / "function-implementations.json"
HERO_PARAGRAPH = re.compile(
    r'(?P<indent>^[ \t]*)<p\s+class="hero-description"[^>]*>.*?</p>',
    flags=re.MULTILINE | re.DOTALL,
)
HERO_SECTION = re.compile(
    r'(?P<body><section\s+class="hero-section".*?)(?P<indent>^[ \t]*)</section>',
    flags=re.MULTILINE | re.DOTALL,
)


def registry(path: Path) -> FunctionRegistry:
    mappings = json.loads(path.read_text(encoding="utf-8"))
    builtins = {"concatenate_monolingual_text": concatenate_monolingual_text}
    result = FunctionRegistry()
    for qid, implementation in mappings.items():
        if implementation not in builtins:
            raise ValueError(f"unknown function implementation {implementation}")
        result.register(qid, builtins[implementation])
    return result


def paragraph_markup(text: str, item: str, function: str, indent: str) -> str:
    return (
        f'{indent}<p class="hero-description" '
        f'data-q315-source="local:{item}" '
        f'data-q315-function="local:{function}">'
        f"{html.escape(text)}</p>"
    )


def update_page(source: str, text: str, item: str, function: str) -> str:
    match = HERO_PARAGRAPH.search(source)
    if match:
        return HERO_PARAGRAPH.sub(
            paragraph_markup(text, item, function, match.group("indent")),
            source,
            count=1,
        )
    section = HERO_SECTION.search(source)
    if section is None:
        raise ValueError("page has neither a hero paragraph nor hero section")
    indent = section.group("indent") + "    "
    addition = "\n\n" + paragraph_markup(text, item, function, indent) + "\n"
    return (
        source[: section.start()]
        + section.group("body")
        + addition
        + section.group("indent")
        + "</section>"
        + source[section.end() :]
    )


def render(repo_root: Path, snapshot: Path, implementations: Path, check: bool) -> int:
    resolver = WikibaseResolver.from_path(snapshot)
    paragraph = resolver.paragraph()
    runtime = registry(implementations)
    group = next(
        group
        for group in load_groups(DEFAULT_MANIFEST, repo_root)
        if group.identifier == "Q3062"
    )
    languages = ("en", "fr", "ml", "pa", "hi", "pt", "es", "it")
    changed = []
    for language, relative_page in zip(languages, group.pages[1:]):
        path = repo_root / relative_page
        source = path.read_text(encoding="utf-8")
        value = runtime.evaluate(resolver.call(paragraph, language))
        updated = update_page(
            source, value.text, paragraph.item, paragraph.function
        )
        if updated != source:
            changed.append(relative_page)
            if not check:
                path.write_text(updated, encoding="utf-8")
    if check and changed:
        for page in changed:
            print(f"STALE: {page}")
        return 1
    action = "Validated" if check else "Rendered"
    print(f"{action} Q3062 hero in {len(languages)} languages")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--implementations", type=Path, default=DEFAULT_IMPLEMENTATIONS
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return render(
        args.repo_root.resolve(),
        args.snapshot,
        args.implementations,
        args.check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
