import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.functions.registry import FunctionRegistry
from abstract.functions.text import concatenate_monolingual_text
from abstract.render_q3062_hero import update_page
from abstract.wikibase_resolver import WikibaseResolver


SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "main"
    / "abstract"
    / "snapshots"
    / "Q3062-hero.json"
)


class WikibaseResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = WikibaseResolver.from_path(SNAPSHOT)
        self.paragraph = self.resolver.paragraph()

    def test_resolves_constructor_and_ordered_parts(self):
        self.assertEqual(self.paragraph.item, "Q3838")
        self.assertEqual(self.paragraph.function, "Q3837")
        self.assertEqual(
            [(ordinal, item) for ordinal, item, _values in self.paragraph.parts],
            [(1, "Q3839"), (2, "Q3840"), (3, "Q3841")],
        )

    def test_resolves_all_eight_languages_from_p40(self):
        expected = {"en", "fr", "ml", "pa", "hi", "pt", "es", "it"}
        for _ordinal, _item, values in self.paragraph.parts:
            self.assertEqual(set(values), expected)

    def test_call_is_evaluated_by_qid_registered_function(self):
        runtime = FunctionRegistry()
        runtime.register("local:Q3837", concatenate_monolingual_text)

        result = runtime.evaluate(self.resolver.call(self.paragraph, "fr"))

        self.assertEqual(result.language, "fr")
        self.assertTrue(result.text.startswith("L'hétérogénéité"))
        self.assertTrue(result.text.endswith("notre monde."))


class HeroPageRenderingTests(unittest.TestCase):
    def test_replaces_existing_hero_paragraph_with_provenance(self):
        source = (
            '<section class="hero-section">\n'
            '  <p class="hero-description">Old.</p>\n'
            "</section>"
        )

        result = update_page(source, "New & safe.", "Q3838", "Q3837")

        self.assertIn("New &amp; safe.", result)
        self.assertIn('data-q315-source="local:Q3838"', result)
        self.assertIn('data-q315-function="local:Q3837"', result)
        self.assertNotIn("Old.", result)

    def test_inserts_missing_hero_paragraph(self):
        source = (
            '<section class="hero-section">\n'
            "  <h1>Title</h1>\n"
            "</section>"
        )

        result = update_page(source, "Generated.", "Q3838", "Q3837")

        self.assertIn('<p class="hero-description"', result)
        self.assertIn(">Generated.</p>", result)


if __name__ == "__main__":
    unittest.main()
