import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.validate_rendered_pages import BoundSlot, is_prose_slot, visible_text


class ProseSlotTests(unittest.TestCase):
    def test_detects_sentence_like_intro_text(self):
        slot = BoundSlot("Q1", "p", "intro-text", ())
        self.assertTrue(
            is_prose_slot(
                slot,
                "A curated collection of visual stories that inspire and educate",
            )
        )

    def test_detects_short_curated_by_subtitle_part(self):
        slot = BoundSlot("Q1", "span", "", ("hero-subtitle",))
        self.assertTrue(is_prose_slot(slot, "Curated by"))

    def test_ignores_place_names_in_subtitle_context(self):
        slot = BoundSlot("Q1", "p", "hero-subtitle", ())
        self.assertFalse(is_prose_slot(slot, "Vienna, Austria"))

    def test_ignores_person_names_in_subtitle_context(self):
        slot = BoundSlot("Q1", "span", "", ("hero-subtitle",))
        self.assertFalse(is_prose_slot(slot, "John Samuel"))


class VisibleTextTests(unittest.TestCase):
    def test_anchor_text_replaces_bare_parentheses(self):
        body = 'collaboration. (<a href="./cv-detailed.html">Detailed CV</a>)'
        self.assertNotIn("()", visible_text(body))

    def test_bare_parentheses_remain_visible(self):
        self.assertIn("()", visible_text("collaboration. ()"))


if __name__ == "__main__":
    unittest.main()
