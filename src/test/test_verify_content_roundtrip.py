import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

import tempfile

from abstract.verify_content_roundtrip import (
    Bindings,
    canonical_value,
    normalize_text,
    rendered_attribute_values,
)


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


class AttributeBindingTests(unittest.TestCase):
    """A description bound to an attribute has to round-trip like any value.

    Without this the renderer could write an image description that nothing ever
    checked again -- the exact blind spot that let a wrong French label sit on
    three pages unnoticed.
    """

    def collect(self, source):
        parser = Bindings()
        parser.feed(source)
        return parser.qids

    def test_an_attribute_binding_is_collected(self):
        found = self.collect('<img class="i" data-content-alt="local:Q9" alt="" />')
        self.assertIn(("data-content-alt", "Q9"), found)

    def test_an_unbindable_attribute_is_ignored(self):
        self.assertEqual(
            self.collect('<img data-content-src="local:Q9" alt="" />'), []
        )

    def test_text_bindings_still_collected_alongside(self):
        found = self.collect(
            '<p data-content="local:Q1">Q1</p>'
            '<img data-content-alt="local:Q2" alt="" />'
        )
        self.assertIn(("data-content", "Q1"), found)
        self.assertIn(("data-content-alt", "Q2"), found)

    def test_rendered_attribute_values_are_read_from_the_page(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False, encoding="utf-8"
        ) as handle:
            handle.write('<img class="i" alt="Arbres à Lyon" src="x" /><p>ignored</p>')
            path = Path(handle.name)
        try:
            self.assertIn("Arbres à Lyon", rendered_attribute_values(path))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
