#!/usr/bin/env python3
"""Verify the language-switcher footer of every Q315-generated language page.

Each page rendered from a Q315 abstract page into one of the site languages must
carry exactly one footer language switcher linking to *every* language the page's
translation group provides, including the page's own language, with the current
language highlighted. Two switcher forms are accepted -- both are styled button
lists that fit their page's theme:

* the ``langlist`` grid used by the travel and profile pages
  (``<li id="{lang}page" class="highlight">`` with a ``langlink`` anchor); and
* the ``lang-selector`` list used by the section pages
  (``<a class="lang-btn active">``).

A page must carry exactly one of these and no second, redundant list -- neither a
duplicate switcher nor a bare ``language-switcher`` nav (the "basic" 8-item list
that is meant to be replaced by a styled switcher).

The set of pages and each page's translation group are taken from the same
``discover()`` registry that drives ``render_page.py``, so the switcher a page is
required to expose always matches the languages that page actually has.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit

_LANGPAGE_ID = re.compile(r"([a-z]{2})page$")
# Classes that mark the current language in a langlist switcher.
_CURRENT_CLASSES = {"highlight", "active"}

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import EXTERNALLY_GENERATED_INDEXES, discover
from abstract.prepare_travel_content import LANGUAGES


@dataclass
class _Link:
    """One language link in a switcher: which language, where it points, active."""

    language: str | None
    href: str
    active: bool


class FooterParser(HTMLParser):
    """Collect the page's language switcher(s), in either accepted form.

    A ``lang-selector`` switcher is a ``<div class="lang-selector">`` whose
    ``lang-btn`` anchors carry no per-language id, so their language is inferred
    later from the href. A ``langlist`` switcher is a ``id="langlist"`` list whose
    ``<li id="{lang}page">`` names the language directly and marks the current one
    with ``class="highlight"``. Both are returned as lists of ``_Link``. A bare
    ``language-switcher`` nav (the basic, unstyled list) is counted separately so
    it can be reported as a switcher that must be replaced.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.switchers: list[list[_Link]] = []
        self.language_switcher_count = 0
        self._depth = 0
        self._switcher_depth: int | None = None
        self._selector = False
        self._li_language: str | None = None
        self._li_active = False

    @staticmethod
    def _classes(attrs: dict[str, str | None]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = self._classes(values)
        if "language-switcher" in classes:
            self.language_switcher_count += 1
        if self._switcher_depth is None:
            if tag == "div" and "lang-selector" in classes:
                self._open_switcher(selector=True)
            elif values.get("id") == "langlist":
                self._open_switcher(selector=False)
        elif not self._selector and tag == "li":
            match = _LANGPAGE_ID.match(values.get("id") or "")
            self._li_language = match.group(1) if match else None
            self._li_active = bool(classes & _CURRENT_CLASSES)
        if tag == "a":
            self._handle_anchor(values, classes)
        self._depth += 1

    def _open_switcher(self, selector: bool) -> None:
        self._switcher_depth = self._depth
        self._selector = selector
        self.switchers.append([])

    def _handle_anchor(
        self, values: dict[str, str | None], classes: set[str]
    ) -> None:
        if self._switcher_depth is None:
            return
        href = values.get("href") or ""
        if self._selector:
            if "lang-btn" in classes:
                self.switchers[-1].append(
                    _Link(language=None, href=href, active="active" in classes)
                )
            return
        # langlist form: the language is named by the <li id="{lang}page"> or,
        # on the plainer pages, by the anchor's own lang attribute; the current
        # link is marked by "highlight" or "active" on either the li or anchor.
        language = values.get("lang") or self._li_language
        if language is None:
            return
        active = self._li_active or bool(classes & _CURRENT_CLASSES)
        if not any(link.language == language for link in self.switchers[-1]):
            self.switchers[-1].append(
                _Link(language=language, href=href, active=active)
            )

    def handle_endtag(self, tag: str) -> None:
        self._depth -= 1
        if self._switcher_depth is not None and self._depth == self._switcher_depth:
            self._switcher_depth = None
            self._li_language = None


@dataclass
class PageResult:
    relative: str
    errors: list[str] = field(default_factory=list)


def _resolve(page: Path, href: str, repo_root: Path) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return None
    candidate = (page.parent / unquote(parsed.path)).resolve()
    try:
        return candidate.relative_to(repo_root.resolve())
    except ValueError:
        return None


def verify_page(
    repo_root: Path, relative: str, current: str, group: dict[str, str]
) -> PageResult:
    result = PageResult(relative=relative)
    page = repo_root / relative
    parser = FooterParser()
    parser.feed(page.read_text(encoding="utf-8"))

    # A bare language-switcher nav counts as a switcher too, so a page that has a
    # styled switcher alongside one is reported as carrying two.
    total = len(parser.switchers) + parser.language_switcher_count
    if total == 0:
        result.errors.append("no language switcher found")
        return result
    if total > 1:
        detail = f"{len(parser.switchers)} styled"
        if parser.language_switcher_count:
            detail += f" + {parser.language_switcher_count} basic language-switcher nav"
        result.errors.append(
            f"{total} language switchers found ({detail}); expected exactly one"
        )
        # Still validate the styled one so its own defects are reported together.
    if not parser.switchers:
        result.errors.append(
            "only a basic language-switcher nav is present; it must be a styled "
            "langlist or lang-selector switcher"
        )
        return result

    links = parser.switchers[0]
    expected = {
        language: (repo_root / target).resolve().relative_to(repo_root.resolve())
        for language, target in group.items()
    }
    resolved = {
        target.as_posix()
        for link in links
        if (target := _resolve(page, link.href, repo_root)) is not None
    }
    for language, target in expected.items():
        if target.as_posix() not in resolved:
            result.errors.append(
                f"missing link for [{language}] -> {target.as_posix()}"
            )
    active = [link for link in links if link.active]
    if len(active) != 1:
        result.errors.append(
            f"expected exactly one highlighted language, found {len(active)}"
        )
    else:
        target = _resolve(page, active[0].href, repo_root)
        own = expected.get(current)
        if own is not None and (target is None or target != own):
            result.errors.append(
                f"highlighted language links to {active[0].href!r}, "
                f"not the current language page {own.as_posix()}"
            )
    return result


def verify(repo_root: Path, page_qid: str = "") -> list[PageResult]:
    rows = [
        row
        for row in discover(repo_root)
        if row["abstract_path"]
        and (not page_qid or row["page_qid"] == page_qid)
        and row.get("target_en", "") not in EXTERNALLY_GENERATED_INDEXES
    ]
    results: list[PageResult] = []
    for row in sorted(rows, key=lambda row: row["page_qid"]):
        group = {
            language: row[f"target_{language}"]
            for language in LANGUAGES
            if row[f"target_{language}"]
        }
        for language, relative in group.items():
            if not (repo_root / relative).is_file():
                continue
            results.append(verify_page(repo_root, relative, language, group))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--page", default="", help="restrict the check to a single abstract page QID"
    )
    parser.add_argument(
        "--max-failing-pages",
        type=int,
        default=0,
        help=(
            "tolerate up to this many pages that still carry a legacy or partial "
            "switcher (a ratchet lowered as pages are converted); the check fails "
            "if the count exceeds the budget"
        ),
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    results = verify(repo_root, args.page)
    failures = [result for result in results if result.errors]
    for result in failures:
        for error in result.errors:
            print(f"FOOTER {result.relative}: {error}")
    print(
        f"Checked {len(results)} Q315 language page(s); "
        f"{len(failures)} with footer problems "
        f"(budget {args.max_failing_pages})"
    )
    return 1 if len(failures) > args.max_failing_pages else 0


if __name__ == "__main__":
    raise SystemExit(main())
