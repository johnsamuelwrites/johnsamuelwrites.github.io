#!/usr/bin/env python3
"""Point every cross-language link at the page's own language when it can.

Q315 templates are built from the English page, so their navigation, breadcrumb
and card links are English-relative, and a language page derived from one keeps
those ``../../en/...`` hrefs. ``render_page.py`` translates the link *text* but
never touches ``href`` (it must not rewrite a URL from a label), so an Italian
page ends up reading "Viaggio" while linking to ``en/travel/index.html`` even
though ``it/viaggi/index.html`` exists.

This tool rewrites such an anchor to its same-language counterpart. Counterparts
come from ``discover()`` -- the Q315 alternates of generated pages plus the
``hreflang`` alternates of legacy en/fr pairs -- so a page with no translation
keeps its link to the language that has it. An anchor is deliberately
cross-language, and left alone, when it carries ``hreflang`` or ``lang`` (a
language toggle, "articles written in English"), wraps a schema.org
``inLanguage`` span, or sits inside a language switcher.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_travel_content import LANGUAGES

# Every switcher variant the site has used, whatever its container element: the
# button list, legacy `ul.language-selector` / `nav.language-switcher` footers and
# the `#langlist` sidebar. Wider than normalize_language_footer's patterns, which
# only match the shapes it replaces.
SWITCHER_RE = re.compile(
    r"<(?P<tag>ul|ol|div|nav)\b[^>]*?(?:\bclass=[\"'][^\"']*\b"
    r"(?:lang-selector|language-selector|language-switcher|language-list)\b"
    r"|\bid=[\"']langlist[\"'])[^>]*>.*?</(?P=tag)>",
    flags=re.IGNORECASE | re.DOTALL,
)
ANCHOR_RE = re.compile(r"<a\b[^>]*>", flags=re.IGNORECASE)
HREF_RE = re.compile(
    r"(?P<prefix>\shref\s*=\s*)(?P<quote>[\"'])(?P<href>.*?)(?P=quote)",
    flags=re.IGNORECASE | re.DOTALL,
)
DELIBERATE_RE = re.compile(r"\s(?:hreflang|lang)\s*=", flags=re.IGNORECASE)
# schema.org markup of a language link: <a ...><span property="inLanguage">.
IN_LANGUAGE_RE = re.compile(r"\bproperty=[\"']inLanguage[\"']", flags=re.IGNORECASE)

Counterparts = dict[str, dict[str, str]]


def counterparts(rows: list[dict[str, str]]) -> Counterparts:
    """Map each concrete page to ``{language: page}`` for its whole group."""
    result: Counterparts = {}
    for row in rows:
        group = {
            language: row[f"target_{language}"]
            for language in LANGUAGES
            if row.get(f"target_{language}")
        }
        if len(group) < 2:
            continue
        for path in group.values():
            result[path] = group
    return result


def page_language(relative: str) -> str:
    first = relative.split("/", 1)[0]
    return first if first in LANGUAGES else ""


def switcher_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in SWITCHER_RE.finditer(text)]


def anchor_body(text: str, end: int) -> str:
    close = text.find("</a", end)
    return text[end:close] if close != -1 else ""


def localize_text(
    text: str,
    page: str,
    groups: Counterparts,
    exists=lambda relative: True,
) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(text, [(old_href, new_href), ...])`` for one page.

    ``page`` and the keys of ``groups`` are repository-relative POSIX paths.
    """
    language = page_language(page)
    if not language:
        return text, []
    spans = switcher_spans(text)
    directory = os.path.dirname(page)
    changes: list[tuple[str, str]] = []

    def rewrite_anchor(anchor: re.Match[str]) -> str:
        tag = anchor.group(0)
        if (
            DELIBERATE_RE.search(tag)
            or IN_LANGUAGE_RE.search(anchor_body(text, anchor.end()))
            or any(start <= anchor.start() < end for start, end in spans)
        ):
            return tag
        href_match = HREF_RE.search(tag)
        if not href_match:
            return tag
        href = html.unescape(href_match.group("href"))
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
            return tag
        target = os.path.normpath(os.path.join(directory, unquote(parsed.path))).replace(
            os.sep, "/"
        )
        target_language = page_language(target)
        if not target_language or target_language == language:
            return tag
        counterpart = groups.get(target, {}).get(language)
        if not counterpart or not exists(counterpart):
            return tag
        localized = os.path.relpath(counterpart, directory or ".").replace(os.sep, "/")
        if parsed.query:
            localized += f"?{parsed.query}"
        if parsed.fragment:
            localized += f"#{parsed.fragment}"
        changes.append((href, localized))
        quote = href_match.group("quote")
        replacement = (
            f"{href_match.group('prefix')}{quote}"
            f"{html.escape(localized, quote=True)}{quote}"
        )
        return tag[: href_match.start()] + replacement + tag[href_match.end() :]

    return ANCHOR_RE.sub(rewrite_anchor, text), changes


def language_pages(repo_root: Path) -> list[Path]:
    return sorted(
        path
        for language in LANGUAGES
        if (repo_root / language).is_dir()
        for path in (repo_root / language).rglob("*.html")
    )


def run(repo_root: Path, check: bool) -> int:
    groups = counterparts(discover(repo_root))

    def exists(relative: str) -> bool:
        return (repo_root / relative).is_file()

    pages = links = 0
    for path in language_pages(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        raw = path.read_bytes()
        original = raw.decode("utf-8")
        text, changes = localize_text(original, relative, groups, exists)
        if not changes:
            continue
        pages += 1
        links += len(changes)
        for old, new in changes:
            print(f"{relative}: {old} -> {new}")
        if not check:
            path.write_bytes(text.encode("utf-8"))
    verb = "need localizing" if check else "localized"
    print(f"{links} cross-language link(s) on {pages} page(s) {verb}")
    return 1 if check and links else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args(argv)
    return run(args.repo_root.resolve(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
