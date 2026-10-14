#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Legacy pages link to their translations.

``link_language_pairs.py`` adds the head alternates and, where a page has no
visible link to a translation, a switcher. Course introduction pages are
paired by rule and their English page's links to last year's French material
are moved onto the copy made at the rollover, leaving past exam questions
alone; other pages are grouped in ``language-groups.csv``.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

import link_language_pairs as pairs

PAGE = """<!DOCTYPE html>
<html lang="{lang}">
  <head>
    <title>Course</title>
  </head>
  <body>
    {body}
  </body>
</html>
"""


class CoursePairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_tool(self, apply):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return pairs.process(self.root, apply, self.root / "groups.csv")

    def test_pair_is_linked_both_ways_and_material_rolled_forward(self):
        fr = self.write(
            "fr/enseignement/cours/2026/IA-DeepLearning/index.html",
            PAGE.format(lang="fr", body='<a href="cours1.html">Cours 1</a>'),
        )
        self.write("fr/enseignement/cours/2026/IA-DeepLearning/cours1.html", "")
        self.write("fr/enseignement/cours/2026/IA-DeepLearning/questions1.html", "")
        old = "../../../../../fr/enseignement/cours/2025/IA-DeepLearning/"
        en = self.write(
            "en/teaching/courses/2026/AI-DeepLearning/index.html",
            PAGE.format(
                lang="en",
                body=f'<a href="{old}cours1.html">Class 1</a>'
                f'<a href="{old}questions1.html">Last exam</a>'
                f'<a href="{old}cours9.html">Dropped class</a>',
            ),
        )

        self.assertEqual(self.run_tool(apply=False), 1)
        self.assertEqual(self.run_tool(apply=True), 0)
        self.assertEqual(self.run_tool(apply=False), 0)

        fr_text, en_text = fr.read_text(), en.read_text()
        en_href = "../../../../../en/teaching/courses/2026/AI-DeepLearning/index.html"
        fr_href = "../../../../../fr/enseignement/cours/2026/IA-DeepLearning/index.html"
        self.assertIn(f'<link rel="alternate" hreflang="en" href="{en_href}" />', fr_text)
        self.assertIn(f'<link rel="alternate" hreflang="fr" href="{fr_href}" />', en_text)
        self.assertIn(f'href="{en_href}" hreflang="en" lang="en">English</a>', fr_text)
        self.assertIn(f'href="{fr_href}" hreflang="fr" lang="fr">Français</a>', en_text)
        self.assertIn("cours/2026/IA-DeepLearning/cours1.html", en_text)
        self.assertIn(f"{old}questions1.html", en_text)
        self.assertIn(f"{old}cours9.html", en_text)

    def test_existing_switcher_is_moved_to_the_same_year(self):
        stale = "../../../../../en/teaching/courses/2025/APDP/index.html"
        fr = self.write(
            "fr/enseignement/cours/2026/APTD/index.html",
            PAGE.format(
                lang="fr",
                body=f'<div class="language-selector"><a href="{stale}" class="lang-btn">English</a></div>',
            ),
        )
        self.write("en/teaching/courses/2026/APDP/index.html", PAGE.format(lang="en", body=""))

        self.run_tool(apply=True)

        text = fr.read_text()
        self.assertNotIn(stale, text)
        self.assertNotIn(pairs.SWITCHER_MARK, text)
        self.assertEqual(text.count("en/teaching/courses/2026/APDP/index.html"), 2)

    def test_csv_group_gets_alternates_and_switcher_only_where_missing(self):
        self.write(
            "groups.csv",
            "en,fr,ml,pa,hi,pt,es,it\n"
            "en/research/apple.html,fr/recherche/pomme.html,,,,,,\n"
            "en/writings/a.html,fr/ecrits/a.html,ml/x/a.html,,,,,\n",
        )
        main = "<main><p>Apple</p></main>"
        en = self.write("en/research/apple.html", PAGE.format(lang="en", body=main))
        fr = self.write("fr/recherche/pomme.html", PAGE.format(lang="fr", body=main))
        links = (
            '<a href="../../en/writings/a.html">en</a><a href="../../fr/ecrits/a.html">fr</a>'
            '<a href="../../ml/x/a.html">ml</a>'
        )
        group = [
            self.write(path, PAGE.format(lang=path[:2], body=links))
            for path in ("en/writings/a.html", "fr/ecrits/a.html", "ml/x/a.html")
        ]

        self.assertEqual(self.run_tool(apply=True), 0)
        self.assertEqual(self.run_tool(apply=False), 0)

        en_text = en.read_text()
        self.assertIn('<link rel="alternate" hreflang="fr" href="../../fr/recherche/pomme.html" />', en_text)
        self.assertIn('class="lang-btn active" href="apple.html" hreflang="en"', en_text)
        self.assertLess(en_text.index(pairs.SWITCHER_MARK), en_text.index("</main>"))
        self.assertIn('href="../../en/research/apple.html" hreflang="en" lang="en">English</a>', fr.read_text())
        ml_text = group[2].read_text()
        self.assertIn('<link rel="alternate" hreflang="en" href="../../en/writings/a.html" />', ml_text)
        self.assertIn('<link rel="alternate" hreflang="fr" href="../../fr/ecrits/a.html" />', ml_text)
        self.assertNotIn(pairs.SWITCHER_MARK, ml_text)

    def test_every_translated_page_in_the_site_is_linked(self):
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            status = pairs.process(pairs.REPO_ROOT, apply=False)
        self.assertEqual(
            status, 0, "run: python src/main/link_language_pairs.py --apply\n" + output.getvalue()
        )


if __name__ == "__main__":
    unittest.main()
