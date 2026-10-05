#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Every published page declares the language it is written in.

A screen reader picks its voice and a search engine its index from
``<html lang>``. Legacy pages were copied from the English ones without
updating it, so most of ``fr/`` announced itself as English.

A page's language is its directory's, except for the pages listed below, which
are written in the other language: English practicals and slides that were
never translated but sit in the French course tree, and talks or courses given
in French that sit in the English one. A new exception must be added here
deliberately. Any ``Content-Language`` meta must agree with ``<html lang>``.
"""

import re
import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from languages import ORDER
from paths import REPO_ROOT

HTML_LANG = re.compile(r'<html\b[^>]*?\slang="([^"]*)"', re.IGNORECASE)
CONTENT_LANGUAGE = re.compile(
    r'<meta\b(?=[^>]*\bhttp-equiv="Content-Language")[^>]*\bcontent="([^"]*)"',
    re.IGNORECASE,
)

WRITTEN_IN_FRENCH = {
    "en/slides/2023/CollectifArchivesLGBTQI+/CollectifArchivesLGBTQI+2023-JohnSamuel.html",
    "en/slides/2023/SASSQueer/SASSQueer2023-JohnSamuel.html",
    "en/slides/2024/CampusduLibre/CampusduLibre2024-JohnSamuel.html",
    "en/teaching/courses/2017/C/class2.html",
    "en/teaching/courses/2017/C/class3.html",
    "en/teaching/courses/2023/DS4C/class2.html",
    "en/teaching/courses/reference/DS4C/class2.html",
}
WRITTEN_IN_ENGLISH = {
    "fr/enseignement/cours/2018/ArchitectureSystemeInformation/cours.html",
    "fr/enseignement/cours/2018/ArchitectureSystemeInformation/cours2.html",
    "fr/enseignement/cours/2019/ArchitectureSystemeInformation/cours1.html",
    "fr/enseignement/cours/référence/ArchitectureSystemeInformation/cours1.html",
    *(
        f"fr/enseignement/cours/{year}/{course}/{page}.html"
        for year in ("2020", "2021")
        for course, pages in (
            ("DataMining", ("projet", "tp0", "tp1", "tp2", "tp3")),
            ("TDM", ("projet", "tp0", "tp1", "tp2", "tp3", "tp4")),
            ("MachineLearning", ("descriptionprojet", "installation")),
        )
        for page in pages
    ),
}
EXCEPTIONS = {
    **{path: "fr" for path in WRITTEN_IN_FRENCH},
    **{path: "en" for path in WRITTEN_IN_ENGLISH},
}


def language_pages():
    for language in ORDER:
        for path in sorted((REPO_ROOT / language).rglob("*.html")):
            yield language, path.relative_to(REPO_ROOT).as_posix(), path


class PageLanguageTests(unittest.TestCase):
    def test_every_page_declares_the_language_it_is_written_in(self):
        wrong = []
        for directory, relative, path in language_pages():
            text = path.read_text(encoding="utf-8", errors="replace")
            match = HTML_LANG.search(text)
            declared = match.group(1) if match else None
            expected = EXCEPTIONS.get(relative, directory)
            if declared != expected:
                wrong.append(f"{relative}: lang={declared!r}, expected {expected!r}")
        self.assertEqual(wrong, [])

    def test_content_language_meta_agrees_with_html_lang(self):
        wrong = []
        for _, relative, path in language_pages():
            text = path.read_text(encoding="utf-8", errors="replace")
            match = HTML_LANG.search(text)
            meta = CONTENT_LANGUAGE.search(text)
            if match and meta and meta.group(1) != match.group(1):
                wrong.append(f"{relative}: lang={match.group(1)!r}, meta={meta.group(1)!r}")
        self.assertEqual(wrong, [])

    def test_exceptions_exist(self):
        missing = [path for path in EXCEPTIONS if not (REPO_ROOT / path).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
