#!/usr/bin/env python3
"""Link every French course introduction page to its English counterpart.

Each year's courses live in two trees: ``fr/enseignement/cours/<year>/<course>/``
(the main one, where the lecture material is) and
``en/teaching/courses/<year>/<course>/``, whose index introduces the course in
English and links back to the French material. The two index pages of a pair
must point at each other, in the same year:

* a ``<link rel="alternate" hreflang>`` in the head, which is also how
  ``discover()`` recognises a legacy en/fr pair;
* a visible language switcher in the body.

Course directories are copied forward at each academic-year rollover, so the
English page of a new year still links to last year's French material. A link
to ``fr/enseignement/cours/<year - 1>/<course>/<file>`` is moved to ``<year>``
when that file exists in the new year's French directory. Exam questions
(``questions*.html``) and links to older years are past sessions, kept on
purpose.

Usage:
    python src/main/link_course_pairs.py --check   # exit 1 if anything is missing
    python src/main/link_course_pairs.py --apply   # fix the pages in place
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_ROOT = Path("fr/enseignement/cours")
EN_ROOT = Path("en/teaching/courses")

# French course directory -> English course directory, where the names differ.
EN_NAME = {
    "Algorithmes": "Algorithms",
    "APTD": "APDP",
    "ArchitectureSystemeInformation": "ArchitectureInformationSystems",
    "IA-DeepLearning": "AI-DeepLearning",
    "PLP": "PPL",
    "ProgSys": "SysProg",
    "Recherche": "Research",
    "TDM": "MDP",
    "TLI": "InternetTechnologyLanguage",
    "TLIA": "AITL",
}

# Both trees sit five levels below the repository root.
UP = "../../../../../"

SWITCHER_CSS = "Q315/assets/css/language-switcher.css"
SWITCHER_MARK = "course-lang-selector"

LABELS = {
    "fr": ("Langue", "Français"),
    "en": ("Language", "English"),
}


def pairs(repo_root: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ``(year, fr_course, en_course)`` pairs and unpaired French pages."""
    found, unpaired = [], []
    for index in sorted((repo_root / FR_ROOT).glob("[0-9]*/*/index.html")):
        year, course = index.parent.parent.name, index.parent.name
        english = EN_NAME.get(course, course)
        if (repo_root / EN_ROOT / year / english / "index.html").is_file():
            found.append((year, course, english))
        else:
            unpaired.append(index.relative_to(repo_root).as_posix())
    return found, unpaired


def page_path(language: str, year: str, course: str) -> str:
    root = FR_ROOT if language == "fr" else EN_ROOT
    return (root / year / course / "index.html").as_posix()


def switcher(language: str, other_href: str, indent: str) -> str:
    other = "en" if language == "fr" else "fr"
    aria, own_name = LABELS[language]
    return (
        f'{indent}<div class="lang-selector {SWITCHER_MARK}" role="navigation" aria-label="{aria}">\n'
        f'{indent}    <a class="lang-btn active" href="index.html" hreflang="{language}" lang="{language}">{own_name}</a>\n'
        f'{indent}    <a class="lang-btn" href="{other_href}" hreflang="{other}" lang="{other}">{LABELS[other][1]}</a>\n'
        f"{indent}</div>\n"
    )


def indent_before(text: str, position: int) -> str:
    line_start = text.rfind("\n", 0, position) + 1
    prefix = text[line_start:position]
    return prefix if not prefix.strip() else ""


def insert_before_last(text: str, tag: str, block: str) -> str:
    position = text.lower().rfind(tag)
    if position < 0:
        return text + block
    line_start = text.rfind("\n", 0, position) + 1
    if text[line_start:position].strip():
        # The tag shares its line with other markup; start a new line.
        return text[:position] + "\n" + block + text[position:]
    return text[:line_start] + block + text[line_start:]


def link_counterpart(text: str, language: str, year: str, course: str, other_course: str) -> tuple[str, list[str]]:
    """Return the page with its counterpart links in place, and what changed."""
    other = "en" if language == "fr" else "fr"
    other_href = UP + page_path(other, year, other_course)
    other_dir = (EN_ROOT if other == "en" else FR_ROOT).as_posix() + "/"
    changes = []

    # A switcher already on the page (APTD carries its own) that names the
    # counterpart from another year: point it at this year.
    stale = re.compile(re.escape(UP + other_dir) + r"(\d{4})/" + re.escape(other_course) + r"/index\.html")
    for match in stale.finditer(text):
        if match.group(1) != year:
            changes.append(f"counterpart link {match.group(1)} -> {year}")
    text = stale.sub(other_href, text)

    head_end = text.lower().find("</head>")
    head = text[:head_end] if head_end >= 0 else ""
    alternate = re.search(r'<link[^>]*rel="alternate"[^>]*hreflang="' + other + r'"', head)
    if not alternate:
        indent = indent_before(text, head_end) + "    " if head_end >= 0 else ""
        link = f'{indent}<link rel="alternate" hreflang="{other}" href="{other_href}" />\n'
        text = insert_before_last(text[: head_end + 7], "</head>", link) + text[head_end + 7 :]
        changes.append("head alternate added")

    has_switcher = SWITCHER_MARK in text or re.search(
        r'class="language-selector"[\s\S]{0,400}?' + re.escape(other_href), text
    )
    if not has_switcher:
        if "</footer>" in text.lower():
            tag = "</footer>"
        else:
            tag = "</body>"
        position = text.lower().rfind(tag)
        indent = indent_before(text, position) + "    " if position >= 0 else ""
        text = insert_before_last(text, tag, switcher(language, other_href, indent))
        if SWITCHER_CSS not in text:
            head_end = text.lower().find("</head>")
            indent = indent_before(text, head_end) + "    "
            css = f'{indent}<link rel="stylesheet" href="{UP}{SWITCHER_CSS}" />\n'
            text = insert_before_last(text[: head_end + 7], "</head>", css) + text[head_end + 7 :]
        changes.append(f"language switcher added ({tag})")
    return text, changes


def roll_material_forward(repo_root: Path, text: str, year: str, fr_course: str) -> tuple[str, list[str]]:
    """Move links to last year's French material onto this year's copy."""
    previous = str(int(year) - 1)
    prefix = f"{FR_ROOT.as_posix()}/{previous}/{fr_course}/"
    pattern = re.compile(re.escape(prefix) + r'([^"#?\s]+)')
    changes = []

    def replace(match: re.Match) -> str:
        name = match.group(1)
        current = FR_ROOT / year / fr_course / name
        if name == "index.html" or name.startswith("questions") or not (repo_root / current).is_file():
            return match.group(0)
        changes.append(f"{previous}/{fr_course}/{name} -> {year}")
        return current.as_posix()

    return pattern.sub(replace, text), changes


def process(repo_root: Path, apply: bool) -> int:
    found, unpaired = pairs(repo_root)
    problems = 0
    for year, fr_course, en_course in found:
        for language, own, other in (("fr", fr_course, en_course), ("en", en_course, fr_course)):
            path = repo_root / page_path(language, year, own)
            original = path.read_text(encoding="utf-8")
            text, changes = link_counterpart(original, language, year, own, other)
            text, rolled = roll_material_forward(repo_root, text, year, fr_course)
            changes += rolled
            if not changes:
                continue
            problems += 1
            relative = path.relative_to(repo_root).as_posix()
            print(f"{relative}: " + "; ".join(changes))
            if apply:
                path.write_text(text, encoding="utf-8")
    for page in unpaired:
        print(f"note: {page} has no English counterpart")
    if problems and not apply:
        print(f"\n{problems} course page(s) need fixing; run with --apply", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report pages needing changes; exit 1 if any")
    mode.add_argument("--apply", action="store_true", help="rewrite the pages in place")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    return process(args.repo_root.resolve(), args.apply)


if __name__ == "__main__":
    sys.exit(main())
