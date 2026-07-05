#!/usr/bin/env python3
"""Rewrite Q315 language pages to a single ``lang-selector`` footer switcher.

The canonical switcher is the ``lang-selector`` button list: one ``lang-btn`` per
language the page's translation group provides, the current language marked
``active``. This module both *renders* that switcher for a page and *normalizes*
an existing page onto it -- expanding a partial (e.g. English/French only)
selector to the full group, and removing any redundant legacy list (the plain
``id="langlist"`` grid or the ``language-switcher`` nav) so a page never ships
two switchers. Pages and groups come from the same ``discover()`` registry as
``render_page.py`` and ``verify_language_footer.py``.

Styling reuses each page's existing theme (``.lang-btn`` and the ``--forest`` /
``--cream`` family of variables), so a page is only safe to convert once its CSS
defines those rules -- see ``css_ready`` and the ``--audit`` mode.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import EXTERNALLY_GENERATED_INDEXES, discover
from abstract.prepare_travel_content import LANGUAGES

# Autonyms shown on each button, matching the site's existing switchers.
LANGUAGE_NAMES = {
    "en": "English",
    "fr": "Français",
    "ml": "മലയാളം",
    "pa": "ਪੰਜਾਬੀ",
    "hi": "हिन्दी",
    "pt": "Português",
    "es": "Español",
    "it": "Italiano",
}

# Rules a page's resolved CSS must provide for the button switcher to render as
# designed. Checked textually against the page and its linked stylesheets.
REQUIRED_CSS_TOKENS = (".lang-selector", ".lang-btn", ".lang-btn.active")

# Relative path (from a language directory such as ``en/``) placeholder is filled
# per page; this is the repo-root-relative location of the shared switcher CSS.
SWITCHER_CSS = "Q315/assets/css/language-switcher.css"

# The existing button switcher (already in the lang-btn form). Attributes such as
# an inline style are tolerated so every variant is matched and de-duplicated.
LANG_SELECTOR_RE = re.compile(
    r'(?P<indent>[ \t]*)<div\b[^>]*\bclass="[^"]*\blang-selector\b[^"]*"[^>]*>'
    r".*?</div>",
    flags=re.DOTALL,
)
# Redundant/legacy switchers that must never survive alongside the button list.
LANGUAGE_SWITCHER_NAV_RE = re.compile(
    r'(?P<indent>[ \t]*)<nav\b[^>]*class="[^"]*\blanguage-switcher\b[^"]*"[^>]*>'
    r".*?</nav>",
    flags=re.DOTALL,
)
# A wrapped list (``<div class="language-selector"><h3>..</h3><ul>..</ul></div>``)
# as used by the home page; the whole wrapper is replaced by the button list.
DIV_LANGUAGE_SELECTOR_RE = re.compile(
    r'(?P<indent>[ \t]*)<div\b[^>]*\bclass="[^"]*\blanguage-selector\b[^"]*"[^>]*>'
    r".*?</div>",
    flags=re.DOTALL,
)
# A bare ``<ul class="language-list">`` as used by the section index/search pages.
UL_LANGUAGE_LIST_RE = re.compile(
    r'(?P<indent>[ \t]*)<ul\b[^>]*class="[^"]*\blanguage-list\b[^"]*"[^>]*>.*?</ul>',
    flags=re.DOTALL,
)
LANGLIST_RE = re.compile(
    r'(?P<indent>[ \t]*)<(?P<tag>ul|ol|div|nav)\b[^>]*\bid="langlist"[^>]*>.*?</(?P=tag)>',
    flags=re.DOTALL,
)
HEAD_CLOSE_RE = re.compile(r"[ \t]*</head>", flags=re.IGNORECASE)


def render_buttons(
    repo_root: Path, page: Path, current: str, group: dict[str, str], indent: str
) -> str:
    """Render the ``lang-btn`` anchors (no wrapping ``lang-selector``)."""
    lines: list[str] = []
    for language in LANGUAGES:
        target = group.get(language)
        if not target:
            continue
        href = os.path.relpath(repo_root / target, page.parent).replace(os.sep, "/")
        classes = "lang-btn active" if language == current else "lang-btn"
        name = html.escape(LANGUAGE_NAMES[language])
        lines.append(
            f'{indent}<a class="{classes}" href="{html.escape(href)}" '
            f'hreflang="{language}" lang="{language}">{name}</a>'
        )
    return "\n".join(lines)


def render_selector(
    repo_root: Path, page: Path, current: str, group: dict[str, str], indent: str
) -> str:
    inner = render_buttons(repo_root, page, current, group, indent + "    ")
    return f'{indent}<div class="lang-selector">\n{inner}\n{indent}</div>'


def css_ready(repo_root: Path, page: Path) -> bool:
    """Whether the page (with its linked stylesheets) styles the switcher."""
    text = page.read_text(encoding="utf-8")
    corpus = [text]
    for tag in re.findall(r"<link\b[^>]*>", text):
        if 'rel="stylesheet"' not in tag:
            continue
        href_match = re.search(r'href="([^"]+)"', tag)
        if not href_match:
            continue
        href = href_match.group(1)
        if href.startswith(("http://", "https://", "//")):
            continue
        asset = (page.parent / href).resolve()
        if asset.is_file():
            corpus.append(asset.read_text(encoding="utf-8"))
    blob = "\n".join(corpus)
    return all(token in blob for token in REQUIRED_CSS_TOKENS)


FOOTER_RE = re.compile(r"<footer\b[^>]*>.*?</footer>", flags=re.DOTALL)
FOOTER_CLOSE_RE = re.compile(r"(?P<indent>[ \t]*)</footer>")
MAIN_CLOSE_RE = re.compile(r"(?P<indent>[ \t]*)</main>")
BODY_CLOSE_RE = re.compile(r"(?P<indent>[ \t]*)</body>", flags=re.IGNORECASE)
# The switcher belongs in the footer, so the footer's own language list is the
# anchor to rewrite; other constructs anywhere on the page are removed. Outer
# wrappers are listed before the lists they contain so stripping never leaves a
# dangling half.
_ANCHOR_PATTERNS = (
    LANG_SELECTOR_RE,
    LANGUAGE_SWITCHER_NAV_RE,
    DIV_LANGUAGE_SELECTOR_RE,
    UL_LANGUAGE_LIST_RE,
    LANGLIST_RE,
)
_PLACEHOLDER = "\x00LANG-SWITCHER-ANCHOR\x00"


def inject_css_link(repo_root: Path, page: Path, text: str) -> str:
    """Ensure the page links the shared switcher stylesheet, once."""
    if SWITCHER_CSS in text:
        return text
    href = os.path.relpath(repo_root / SWITCHER_CSS, page.parent).replace(os.sep, "/")
    match = HEAD_CLOSE_RE.search(text)
    if not match:
        return text
    indent = match.group(0)[: len(match.group(0)) - len("</head>")]
    link = f'{indent}<link rel="stylesheet" href="{html.escape(href)}" />\n'
    return text[: match.start()] + "\n" + link + text[match.start() :].lstrip("\n")


def _anchor_in_footer(text: str) -> tuple[int, int, str] | None:
    """Locate the footer's language list to replace: ``(start, end, indent)``.

    Returns ``None`` when the page has a footer but no recognised list inside it,
    so the caller can insert a fresh switcher before ``</footer>``.
    """
    footer = FOOTER_RE.search(text)
    if not footer:
        return None
    start, end = footer.span()
    best: tuple[int, int, str] | None = None
    for pattern in _ANCHOR_PATTERNS:
        for match in pattern.finditer(text, start, end):
            indent = match.groupdict().get("indent") or ""
            if best is None or match.start() < best[0]:
                best = (match.start(), match.end(), indent)
        if best is not None:
            return best
    return None


def _add_footer(
    repo_root: Path, page: Path, current: str, group: dict[str, str], text: str
) -> str | None:
    """Create a footer holding the switcher on a page that lacks one."""
    match = MAIN_CLOSE_RE.search(text) or BODY_CLOSE_RE.search(text)
    if not match:
        return None
    indent = match.group("indent")
    selector = render_selector(repo_root, page, current, group, indent + "    ")
    footer = f'{indent}<footer class="footer">\n{selector}\n{indent}</footer>\n'
    if match.re is MAIN_CLOSE_RE:
        # Place the footer after </main>.
        insert_at = match.end()
        return text[:insert_at] + "\n" + footer + text[insert_at:]
    # Place it before </body>.
    return text[: match.start()] + footer + text[match.start() :]


def normalize(
    repo_root: Path, page: Path, current: str, group: dict[str, str]
) -> tuple[str, bool]:
    """Return ``(new_text, changed)`` for a single page."""
    original = page.read_text(encoding="utf-8")
    if not FOOTER_RE.search(original):
        created = _add_footer(repo_root, page, current, group, original)
        if created is None:
            return original, False
        return inject_css_link(repo_root, page, created), True

    anchor = _anchor_in_footer(original)
    if anchor is not None:
        start, end, indent = anchor
        text = original[:start] + _PLACEHOLDER + original[end:]
    else:
        # No list in the footer: place one just before </footer>.
        close = FOOTER_CLOSE_RE.search(original)
        if not close:
            return original, False
        indent = close.group("indent") + "    "
        text = (
            original[: close.start()]
            + _PLACEHOLDER
            + "\n"
            + close.group(0)
            + original[close.end() :]
        )

    # Remove every other language list left on the page (a top-of-page selector,
    # a redundant nav, a second grid); the anchor is safe behind its placeholder.
    for pattern in _ANCHOR_PATTERNS:
        text = pattern.sub("", text)

    # The placeholder consumed the anchor's own leading indent, so the rendered
    # selector (which carries that indent) drops straight in.
    selector = render_selector(repo_root, page, current, group, indent)
    text = text.replace(_PLACEHOLDER, selector, 1)
    text = inject_css_link(repo_root, page, text)
    return text, (text != original)


def rows_for(repo_root: Path, page_qid: str) -> list[dict[str, str]]:
    return [
        row
        for row in discover(repo_root)
        if row["abstract_path"]
        and (not page_qid or row["page_qid"] == page_qid)
        and row.get("target_en", "") not in EXTERNALLY_GENERATED_INDEXES
    ]


def run(
    repo_root: Path, page_qid: str, apply: bool, audit: bool
) -> int:
    changed: list[str] = []
    no_anchor: list[str] = []
    for row in sorted(rows_for(repo_root, page_qid), key=lambda row: row["page_qid"]):
        group = {
            language: row[f"target_{language}"]
            for language in LANGUAGES
            if row[f"target_{language}"]
        }
        for language, relative in group.items():
            page = repo_root / relative
            if not page.is_file():
                continue
            new_text, did_change = normalize(repo_root, page, language, group)
            if audit:
                if 'class="lang-selector"' not in new_text:
                    no_anchor.append(relative)
                continue
            if 'class="lang-selector"' not in new_text:
                no_anchor.append(relative)
                continue
            if did_change:
                changed.append(relative)
                if apply:
                    page.write_text(new_text, encoding="utf-8")

    for relative in sorted(no_anchor):
        print(f"NO-ANCHOR {relative}")
    verb = "Rewrote" if (apply and not audit) else "Would rewrite"
    print(
        f"{verb} {len(changed)} page(s); "
        f"{len(no_anchor)} with no language list to rewrite"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--page", default="", help="restrict to a single abstract QID")
    parser.add_argument("--apply", action="store_true", help="write changes to disk")
    parser.add_argument(
        "--audit",
        action="store_true",
        help="only report CSS readiness; never rewrite",
    )
    args = parser.parse_args(argv)
    return run(args.repo_root.resolve(), args.page, args.apply, args.audit)


if __name__ == "__main__":
    raise SystemExit(main())
