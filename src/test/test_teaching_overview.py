#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The teaching overview pages are generated from data/teaching/courses.csv.

``teaching_overview.py`` reads the recorded years, links each year's course
page in the reader's language (falling back to the other one, marked with
``hreflang``), and splits the cards into current and past courses.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

import teaching_overview as overview

HEADER = (
    "id,title_fr,title_en,title_item,programme_fr,programme_en,major,study_year,responsibility_fr,"
    "responsibility_en,roles_fr,roles_en,ects,hours,instruction,taught,pages,theme,follows,notes\n"
)
INDEX = """<nav class="site-navigation"><a class="nav-name" href="../about.html">John Samuel</a>
<ul class="nav-links"><li><a href="../index.html">Home {lang}</a></li><li><a href="./index.html">Teaching {lang}</a></li></ul>
</nav>"""


class TaughtYearsTests(unittest.TestCase):
    def test_recorded_forms(self):
        self.assertEqual(overview.parse_taught("2024-", 2026), ([2024, 2025, 2026], True))
        self.assertEqual(overview.parse_taught("2017-2019", 2026), ([2017, 2018, 2019], False))
        self.assertEqual(overview.parse_taught("2017, 2018, 2022", 2026), ([2017, 2018, 2022], False))
        with self.assertRaises(ValueError):
            overview.parse_taught("since 2017", 2026)


class GeneratedPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # The real translation table and page shell; a teaching index per language.
        for relative in (overview.STRINGS, overview.TEMPLATE):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(overview.REPO_ROOT / relative, target)
        strings = overview.Strings(self.root / overview.STRINGS)
        for language in overview.ORDER:
            page = Path(strings.get("page_path", language))
            self.write(page.parent / "index.html", INDEX.format(lang=language))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text=""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_pages_are_generated_with_language_fallback_and_current_split(self):
        self.write("fr/enseignement/cours/2025/C/index.html")
        self.write("fr/enseignement/cours/2026/C/index.html")
        self.write("en/teaching/courses/2026/C/index.html")
        self.write("en/teaching/courses/2017/InternetTechnologyLanguage/index.html")
        self.write(
            "data/teaching/courses.csv",
            HEADER
            + "c,Programmation en C,Programming in C,Q5666,ETI,ETI,,4,Responsable,Instructor,,,3,36,fr,2025-,2025:C 2026:C,programming,,\n"
            + "tli,Technologies,Internet,title:tli,IRC,IRC,,3,Responsable,Instructor,,,3,36,fr,2017,2017:TLI,web,?c,\n",
        )
        self.assertEqual(overview.process(self.root, apply=False), 1)
        self.assertEqual(overview.process(self.root, apply=True), 0)
        self.assertEqual(overview.process(self.root, apply=False), 0)

        fr = (self.root / "fr/enseignement/enseignement.html").read_text(encoding="utf-8")
        en = (self.root / "en/teaching/teaching.html").read_text(encoding="utf-8")
        es = (self.root / "es/enseñanza/enseñanza.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="fr">', fr)
        self.assertIn("Home fr", fr)
        self.assertIn('hreflang="es" href="../../es/enseñanza/enseñanza.html"', fr)
        self.assertIn('class="lang-btn active" hreflang="es" lang="es">Español</a>', es)
        self.assertIn('href="./cours/2025/C/index.html"', fr)
        # TLI 2017 exists only in English: the French page links it, marked.
        self.assertIn('href="../../en/teaching/courses/2017/InternetTechnologyLanguage/index.html" hreflang="en"', fr)
        # 2025 C exists only in French: the English page links it, marked.
        self.assertIn('href="../../fr/enseignement/cours/2025/C/index.html" hreflang="fr"', en)
        self.assertIn('href="./courses/2026/C/index.html"', en)
        self.assertLess(fr.index("Modules actuels"), fr.index('data-id="c"', fr.index("Modules actuels")))
        self.assertLess(fr.index("Anciens modules"), fr.index('class="course-card" data-id="tli"'))
        self.assertIn('class="lineage proposed" data-from="c" data-to="tli"', fr)
        self.assertIn('<div class="year-summary" data-year="2026" hidden>', en)
        # Other languages: translated interface, English course pages first.
        self.assertIn("Cursos actuales", es)
        self.assertIn("Tecnologías y lenguajes de Internet (IRC)", es)
        self.assertIn('href="../../en/teaching/courses/2026/C/index.html" hreflang="en"', es)
        self.assertIn('href="../../fr/enseignement/cours/2025/C/index.html" hreflang="fr"', es)

    def test_bad_data_is_refused(self):
        self.write("fr/enseignement/cours/2026/C/index.html")
        self.write(
            "data/teaching/courses.csv",
            HEADER + "c,C,C,title:nowhere,ETI,ETI,,4,R,R,,,3,36,fr,2026-,2026:C 2026:Missing,nonsense,ghost,\n",
        )
        with self.assertRaises(SystemExit) as raised:
            overview.load(self.root)
        message = str(raised.exception)
        self.assertIn("no course page for 2026:Missing", message)
        self.assertIn("unknown theme 'nonsense'", message)
        self.assertIn("follows unknown id 'ghost'", message)
        self.assertIn("no translation row 'title:nowhere'", message)

    def test_site_pages_match_the_data(self):
        self.assertEqual(
            overview.process(overview.REPO_ROOT, apply=False),
            0,
            "run: python src/main/teaching_overview.py --apply",
        )


if __name__ == "__main__":
    unittest.main()
