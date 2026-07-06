import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.verify_content_roundtrip import canonical_value, normalize_text


class CanonicalValueTests(unittest.TestCase):
    def test_decodes_quotes_escaped_by_the_wikibase_csv_export(self):
        self.assertEqual(
            canonical_value(r'\"Photography is a way of feeling.'),
            '"Photography is a way of feeling.',
        )

    def test_collapses_visible_whitespace(self):
        self.assertEqual(canonical_value("one\n  two"), "one two")


class NormalizeTextTests(unittest.TestCase):
    def test_folds_typographic_apostrophe_to_straight(self):
        self.assertEqual(
            normalize_text("l’ascension d’un tableau"),
            "l'ascension d'un tableau",
        )

    def test_folds_curly_double_quotes(self):
        self.assertEqual(normalize_text("“Salvator Mundi”"), '"Salvator Mundi"')

    def test_folds_dashes_and_ellipsis(self):
        self.assertEqual(normalize_text("Sunset — dusk…"), "Sunset - dusk...")

    def test_folds_non_breaking_space_and_collapses_whitespace(self):
        self.assertEqual(normalize_text("one  two\n three"), "one two three")

    def test_leaves_matching_text_unchanged(self):
        self.assertEqual(normalize_text("Steven Pinker"), "Steven Pinker")


if __name__ == "__main__":
    unittest.main()
