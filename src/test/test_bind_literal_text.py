#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Literal text on an abstract page becomes a bound slot, never a guess."""

import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "abstract"))

from abstract.bind_literal_text import bind_text, literal_slots, majority

PAGE = (
    "<ul>\n"
    '  <li class="card"><h3 class="title" data-content="local:Q8055">Q8055</h3>\n'
    '    <div class="course-year">\n      3rd year, CPE Lyon\n    </div></li>\n'
    '  <li class="card"><div class="course-year">Q8060</div>'
    "<div class=\"note\">See <a href='x'>Q5</a></div></li>\n"
    "</ul>\n"
)
YEAR = ("div", "course-year", "", 0)


class LiteralSlotTests(unittest.TestCase):
    def test_only_unbound_literal_text_elements_are_slots(self):
        found = literal_slots(PAGE)
        self.assertEqual(set(found), {YEAR})
        self.assertEqual(found[YEAR].text, "3rd year, CPE Lyon")

    def test_marked_elements_are_not_slots(self):
        page = '<a lang="en" href="x">Learning a language</a><b translate="no">CPE Lyon</b><i>Photos</i>'
        self.assertEqual([slot.text for slot in literal_slots(page).values()], ["Photos"])

    def test_an_element_with_child_elements_is_not_a_slot(self):
        self.assertNotIn(("div", "note", "", 0), literal_slots(PAGE))


class BindTextTests(unittest.TestCase):
    def test_a_slot_is_bound_and_shows_its_qid(self):
        text, count = bind_text(PAGE, {YEAR: "Q8056"})
        self.assertEqual(count, 1)
        self.assertIn('<div class="course-year" data-content="local:Q8056">\n      Q8056\n    </div>', text)
        self.assertNotIn("3rd year", text)

    def test_binding_twice_changes_nothing(self):
        once, _ = bind_text(PAGE, {YEAR: "Q8056"})
        twice, count = bind_text(once, {YEAR: "Q1"})
        self.assertEqual((twice, count), (once, 0))

    def test_the_rest_of_the_page_is_untouched(self):
        text, _ = bind_text(PAGE, {YEAR: "Q8056"})
        self.assertIn('data-content="local:Q8055">Q8055</h3>', text)
        self.assertIn("See <a href='x'>Q5</a>", text)


class MajorityTests(unittest.TestCase):
    def test_the_most_frequent_translation_wins_per_english_text(self):
        found = {
            1: {"en": "4th year, CPE Lyon", "pa": "ਚੌਥਾ ਸਾਲ"},
            2: {"en": "4th year, CPE Lyon", "pa": "ਚੌਥਾ ਸਾਲ"},
            3: {"en": "4th year, CPE Lyon", "pa": "4ਵਾਂ ਸਾਲ"},
        }
        self.assertEqual(majority(found)["4th year, CPE Lyon"]["pa"], "ਚੌਥਾ ਸਾਲ")


if __name__ == "__main__":
    unittest.main()
