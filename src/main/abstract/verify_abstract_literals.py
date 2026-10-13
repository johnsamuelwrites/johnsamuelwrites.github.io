#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Find natural-language literals left in the canonical Q315 pages.

An abstract page holds content as QIDs; ``render_page.py`` writes each
language's text from them. A literal instead -- English text in an element, or
in an attribute the page displays -- reaches every language page unchanged, and
nothing else notices: the renderer has nothing bound to rewrite, and the
round-trip check only compares bound values. That is how gallery captions
(``data-location``) shipped in English to every language.

Two kinds of literal are reported:

* visible text that is not made of QIDs (outside scripts, styles, SVG, code
  and function calls), except the language switcher's endonyms, which name each
  language in itself on purpose, and a bare path or file name (no spaces, a
  ``/`` or an extension), which is an identifier rather than prose;
* values of attributes that carry prose: the bindable attributes, plus every
  attribute a Q315 stylesheet displays with CSS ``attr()``, discovered from the
  stylesheets so a new one is covered without editing this file.

Text the page marks as deliberately not Q315 content is not a literal: an
element (or ancestor) with ``lang`` other than ``zxx`` holds text in that
language on purpose -- the title of an article, quoted as published -- and
``translate="no"`` marks a name that stays as written (ORCID, CPE Lyon, an
address). Both are standard HTML and tell readers and tools the same thing.

``--max-literals`` is a ratchet like ``verify_language_footer.py``'s budget:
lower it as literals are converted to QIDs; the check fails as soon as a new
one appears.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.render_page import BINDABLE_ATTRIBUTES

PATH = re.compile(r"\S*(?:/\S*|\.[a-z0-9]{2,5})")
QID_TEXT = re.compile(r"(?:Q[1-9][0-9]*[\s,;:•·|/()\-–—.]*)+")
WORD = re.compile(r"[^\W\d_]{2}")
CSS_ATTR = re.compile(r"\battr\(\s*([a-zA-Z][\w-]*)\s*\)")
SKIPPED = frozenset({"script", "style", "svg", "code", "pre", "math", "q-call"})
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                  "meta", "param", "source", "track", "wbr"})
# The language switcher names each language in that language on every page.
ENDONYMS = frozenset({"English", "Français", "മലയാളം", "ਪੰਜਾਬੀ", "हिन्दी",
                      "Português", "Español", "Italiano"})


def displayed_attributes(stylesheets: Iterable[Path]) -> set[str]:
    """Attributes a stylesheet shows to readers through ``attr()``."""
    found: set[str] = set()
    for path in stylesheets:
        found.update(CSS_ATTR.findall(path.read_text(encoding="utf-8", errors="replace")))
    return found


def is_literal(value: str) -> bool:
    value = " ".join(value.split())
    return (
        bool(value)
        and bool(WORD.search(value))
        and not QID_TEXT.fullmatch(value)
        and not PATH.fullmatch(value)
    )


class Literals(HTMLParser):
    """Collect ``(line, where, text)`` for every literal on one page."""

    def __init__(self, prose_attributes: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.prose_attributes = prose_attributes
        self.stack: list[str] = []
        # Whether each open element is marked as not Q315 content.
        self.exempt: list[bool] = []
        self.found: list[tuple[int, str, str]] = []

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        language = (values.get("lang") or "").strip()
        exempt = (bool(self.exempt) and self.exempt[-1]) or values.get("translate") == "no" or (
            bool(language) and language != "zxx"
        )
        for name, value in attrs:
            if name in self.prose_attributes and not exempt and is_literal(value or ""):
                self.found.append((self.getpos()[0], f"<{tag} {name}>", " ".join((value or "").split())))
        if tag not in VOID:
            self.stack.append(tag)
            self.exempt.append(exempt)

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()
            self.exempt.pop()

    def handle_endtag(self, tag) -> None:
        if tag not in self.stack:
            return
        while self.stack:
            self.exempt.pop()
            if self.stack.pop() == tag:
                break

    def handle_data(self, data) -> None:
        text = " ".join(data.split())
        if not is_literal(text) or text in ENDONYMS or SKIPPED.intersection(self.stack):
            return
        if self.exempt and self.exempt[-1]:
            return
        self.found.append((self.getpos()[0], f"<{self.stack[-1] if self.stack else ''}>", text))


def literals(path: Path, prose_attributes: set[str]) -> list[tuple[int, str, str]]:
    parser = Literals(prose_attributes)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser.found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--max-literals",
        type=int,
        default=0,
        help="tolerate up to this many literals (a ratchet lowered as they are "
        "converted); the check fails if the count exceeds the budget",
    )
    parser.add_argument("--verbose", action="store_true", help="list every literal")
    args = parser.parse_args(argv)

    root = args.repo_root.resolve() / "Q315"
    prose = set(BINDABLE_ATTRIBUTES) | displayed_attributes(root.rglob("*.css"))
    found: dict[Path, list[tuple[int, str, str]]] = {}
    for path in sorted(root.rglob("*.html")):
        page = literals(path, prose)
        if page:
            found[path] = page
    total = sum(len(page) for page in found.values())

    by_where = collections.Counter(where for page in found.values() for _line, where, _text in page)
    for path, page in found.items():
        relative = path.relative_to(root.parent)
        shown = page if args.verbose else page[:3]
        for line, where, text in shown:
            print(f"{relative}:{line}: {where} {text[:100]!r}")
        if len(shown) < len(page):
            print(f"{relative}: ... {len(page) - len(shown)} more")
    print(f"Prose attributes checked: {', '.join(sorted(prose))}")
    print(f"Most common places: {', '.join(f'{w} {n}' for w, n in by_where.most_common(6))}")
    print(
        f"Found {total} literal(s) on {len(found)} Q315 page(s) "
        f"(budget {args.max_literals})"
    )
    return 1 if total > args.max_literals else 0


if __name__ == "__main__":
    raise SystemExit(main())
