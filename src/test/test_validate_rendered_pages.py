import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract import validate_rendered_pages as guard
from abstract.validate_rendered_pages import BoundSlot, is_prose_slot, visible_text
from abstract.verify_content_roundtrip import rendered_bound_values, rendered_equivalent_values


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


class StructuralParityTests(unittest.TestCase):
    def test_reports_missing_hero_svg_from_rendered_language_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Q315").mkdir()
            (root / "Q315" / "page.html").write_text(
                '<section><svg class="hero-svg"></svg></section>',
                encoding="utf-8",
            )
            (root / "ml.html").write_text("<section></section>", encoding="utf-8")
            rows = [
                {
                    "page_qid": "QTEST",
                    "abstract_path": "Q315/page.html",
                    "target_ml": "ml.html",
                }
            ]

            with patch.object(guard, "discover", return_value=rows), patch.object(
                guard, "LANGUAGES", ("ml",)
            ):
                errors = guard.structural_parity_errors(root, "QTEST")

        self.assertEqual(1, len(errors))
        self.assertIn("hero SVG count differs", errors[0])


class RoundTripRenderedTextTests(unittest.TestCase):
    def test_rendered_bound_text_includes_inline_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.html"
            path.write_text(
                '<p data-q315-source="local:Q1"><b>Title</b>, Author</p>',
                encoding="utf-8",
            )

            self.assertEqual(["Title, Author"], rendered_bound_values(path))

    def test_rendered_equivalent_values_accepts_link_label(self):
        self.assertIn(
            "Title, Author, Venue, 2026 (Link)",
            rendered_equivalent_values(
                "Title, Author, Venue, 2026, https://example.org/paper"
            ),
        )
        self.assertIn(
            "Title, Author, Venue, 2026 (Lien)",
            rendered_equivalent_values(
                "Title, Author, Venue, 2026, https://example.org/paper"
            ),
        )


if __name__ == "__main__":
    unittest.main()
