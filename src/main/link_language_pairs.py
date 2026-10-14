#!/usr/bin/env python3
"""Link legacy pages to their translations in the other site languages.

Pages rendered from Q315 get their language footer from the Q315 pipeline.
Legacy pages that exist in several languages are linked here instead. A group
of translations is either

* a course introduction page: ``fr/enseignement/cours/<year>/<course>/`` (the
  main tree, where the lecture material is) and its English page in
  ``en/teaching/courses/<year>/<course>/``, paired by rule; or
* a row of ``abstract/data/language-groups.csv`` (one column per language, an
  empty cell where the page has no translation).

Every page of a group must declare each other member with a
``<link rel="alternate" hreflang>`` in its head (this is also how
``discover()`` recognises a legacy pair) and link to it visibly. A page that
lacks a visible link gets a ``lang-selector`` switcher, at the end of its
footer, else of its ``<main>``, else of its body.

Course directories are copied forward at each academic-year rollover, so the
English page of a new year still links to last year's French material. A link
to ``fr/enseignement/cours/<year - 1>/<course>/<file>`` is moved to ``<year>``
when that file exists in the new year's French directory. Exam questions
(``questions*.html``) and links to older years are past sessions, kept on
purpose.

Usage:
    python src/main/link_language_pairs.py --check   # exit 1 if anything is missing
    python src/main/link_language_pairs.py --apply   # fix the pages in place
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from languages import ENDONYMS, ORDER

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUPS_CSV = Path(__file__).resolve().parent / "abstract" / "data" / "language-groups.csv"
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

SWITCHER_CSS = Path("Q315/assets/css/language-switcher.css")
SWITCHER_MARK = "course-lang-selector"
ARIA_LABEL = {"en": "Language", "fr": "Langue"}

ANCHOR = re.compile(r'<a\b[^>]*?\bhref="([^"]*)"', re.IGNORECASE)
ALTERNATE = re.compile(r'<link\b[^>]*rel="alternate"[^>]*>', re.IGNORECASE)


class Group:
    """Translations of one page: ``{language: repository path}``."""

    def __init__(self, members: dict[str, str], course: tuple[str, str, str] | None = None):
        self.members = members
        # (year, French course, English course) for a course introduction pair.
        self.course = course


def course_groups(repo_root: Path) -> tuple[list[Group], list[str]]:
    """Return the course introduction pairs and unpaired French pages."""
    found, unpaired = [], []
    for index in sorted((repo_root / FR_ROOT).glob("[0-9]*/*/index.html")):
        year, course = index.parent.parent.name, index.parent.name
        english = EN_NAME.get(course, course)
        en_index = EN_ROOT / year / english / "index.html"
        if (repo_root / en_index).is_file():
            members = {"fr": index.relative_to(repo_root).as_posix(), "en": en_index.as_posix()}
            found.append(Group(members, (year, course, english)))
        else:
            unpaired.append(index.relative_to(repo_root).as_posix())
    return found, unpaired


def csv_groups(path: Path) -> list[Group]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            Group({language: row[language] for language in ORDER if row.get(language)})
            for row in csv.DictReader(handle)
        ]


def relative(source: str, target: str | Path) -> str:
    return os.path.relpath(Path(target), Path(source).parent).replace(os.sep, "/")


def resolve(source: str, href: str) -> str | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(source), unquote(parsed.path))).replace(os.sep, "/")


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


def insert_in_head(text: str, line: str) -> str:
    head_end = text.lower().find("</head>")
    indent = indent_before(text, head_end) + "    "
    end = head_end + len("</head>")
    return insert_before_last(text[:end], "</head>", indent + line + "\n") + text[end:]


def switcher(page: str, language: str, members: dict[str, str], indent: str) -> str:
    lines = [
        f'{indent}<div class="lang-selector {SWITCHER_MARK}" role="navigation" '
        f'aria-label="{ARIA_LABEL.get(language, ARIA_LABEL["en"])}">\n'
    ]
    for code in ORDER:
        if code not in members:
            continue
        if code == language:
            attributes, href = 'class="lang-btn active"', Path(page).name
        else:
            attributes, href = 'class="lang-btn"', relative(page, members[code])
        lines.append(
            f'{indent}    <a {attributes} href="{href}" hreflang="{code}" lang="{code}">{ENDONYMS[code]}</a>\n'
        )
    lines.append(f"{indent}</div>\n")
    return "".join(lines)


def fix_stale_course_switcher(text: str, page: str, group: Group) -> tuple[str, list[str]]:
    """Point a course switcher that names last year's counterpart at this year."""
    year, fr_course, en_course = group.course
    language = page.split("/")[0]
    other = "en" if language == "fr" else "fr"
    other_course = en_course if other == "en" else fr_course
    other_href = relative(page, group.members[other])
    up = other_href[: other_href.index(other + "/")]
    other_dir = (EN_ROOT if other == "en" else FR_ROOT).as_posix() + "/"
    stale = re.compile(re.escape(up + other_dir) + r"(\d{4})/" + re.escape(other_course) + r"/index\.html")
    changes = [
        f"counterpart link {match.group(1)} -> {year}"
        for match in stale.finditer(text)
        if match.group(1) != year
    ]
    return stale.sub(other_href, text), changes


def link_group_page(text: str, page: str, group: Group) -> tuple[str, list[str]]:
    """Return the page with head alternates and a visible link to every member."""
    language = page.split("/")[0]
    others = {code: path for code, path in group.members.items() if code != language}
    changes = []
    if group.course:
        text, changes = fix_stale_course_switcher(text, page, group)

    head_end = text.lower().find("</head>")
    declared = {}
    for match in ALTERNATE.finditer(text[:head_end]):
        hreflang = re.search(r'hreflang="([^"]*)"', match.group(0))
        if hreflang:
            declared[hreflang.group(1)] = match
    for code, target in others.items():
        href = relative(page, target)
        existing = declared.get(code)
        if existing is None:
            text = insert_in_head(text, f'<link rel="alternate" hreflang="{code}" href="{href}" />')
            changes.append(f"head alternate {code} added")
        else:
            current = re.search(r'href="([^"]*)"', existing.group(0))
            if current and resolve(page, current.group(1)) != target:
                fixed = existing.group(0).replace(current.group(0), f'href="{href}"')
                text = text.replace(existing.group(0), fixed, 1)
                changes.append(f"head alternate {code} corrected")

    body = text[text.lower().find("</head>") :]
    linked = {resolve(page, href) for href in ANCHOR.findall(body)}
    if any(target not in linked for target in others.values()):
        lower = text.lower()
        tag = next(tag for tag in ("</footer>", "</main>", "</body>") if tag in lower or tag == "</body>")
        position = text.lower().rfind(tag)
        indent = indent_before(text, position) + "    " if position >= 0 else ""
        text = insert_before_last(text, tag, switcher(page, language, group.members, indent))
        css = relative(page, SWITCHER_CSS)
        if css not in text:
            text = insert_in_head(text, f'<link rel="stylesheet" href="{css}" />')
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


def process(repo_root: Path, apply: bool, groups_csv: Path = GROUPS_CSV) -> int:
    groups, unpaired = course_groups(repo_root)
    if groups_csv.is_file():
        groups += csv_groups(groups_csv)
    problems = 0
    for group in groups:
        missing = [path for path in group.members.values() if not (repo_root / path).is_file()]
        if missing:
            problems += 1
            print(f"missing page(s) in group: {', '.join(missing)}")
            continue
        for page in group.members.values():
            path = repo_root / page
            text, changes = link_group_page(path.read_text(encoding="utf-8"), page, group)
            if group.course:
                year, fr_course, _ = group.course
                text, rolled = roll_material_forward(repo_root, text, year, fr_course)
                changes += rolled
            if not changes:
                continue
            problems += 1
            print(f"{page}: " + "; ".join(changes))
            if apply:
                path.write_text(text, encoding="utf-8")
    for page in unpaired:
        print(f"note: {page} has no English counterpart")
    if problems and not apply:
        print(f"\n{problems} page(s) need fixing; run with --apply", file=sys.stderr)
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
