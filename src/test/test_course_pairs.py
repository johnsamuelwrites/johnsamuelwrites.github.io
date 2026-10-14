#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""French and English course introduction pages link to each other.

``link_course_pairs.py`` adds the head alternate and the visible switcher to
both pages of a year's pair, and moves links to last year's French material
onto the copy made at the rollover, leaving past exam questions alone.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

import link_course_pairs as pairs

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
            return pairs.process(self.root, apply)

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

    def test_every_course_page_in_the_site_is_linked(self):
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            status = pairs.process(pairs.REPO_ROOT, apply=False)
        self.assertEqual(
            status, 0, "run: python src/main/link_course_pairs.py --apply\n" + output.getvalue()
        )


if __name__ == "__main__":
    unittest.main()
