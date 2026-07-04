import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.functions.registry import (
    COMPOSE_PARAGRAPH_BOOTSTRAP_KEY,
    default_registry,
)
from abstract.functions.text import compose_ordered_paragraph
from abstract.model import FunctionCall, MonolingualText
from abstract.render_abstract import registry


def sentences(language, *texts):
    return [MonolingualText(language, text) for text in texts]


class ComposeOrderedParagraphTests(unittest.TestCase):
    def test_space_separated_languages_join_with_one_space(self):
        result = compose_ordered_paragraph(
            parts=sentences("en", "One sentence.", "Another sentence."),
            language="en",
        )
        self.assertEqual(result.text, "One sentence. Another sentence.")
        self.assertEqual(result.language, "en")

    def test_spacing_is_derived_from_language_not_the_caller(self):
        result = compose_ordered_paragraph(
            parts=sentences("ja", "文一。", "文二。"), language="ja"
        )
        self.assertEqual(result.text, "文一。文二。")

    def test_a_language_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            compose_ordered_paragraph(
                parts=[MonolingualText("fr", "Une phrase.")], language="en"
            )

    def test_an_empty_paragraph_is_rejected(self):
        with self.assertRaises(ValueError):
            compose_ordered_paragraph(parts=[], language="en")


class RegistryWiringTests(unittest.TestCase):
    def test_default_registry_evaluates_the_bootstrap_function(self):
        call = FunctionCall(
            function_id=COMPOSE_PARAGRAPH_BOOTSTRAP_KEY,
            arguments={
                "parts": sentences("fr", "Phrase une.", "Phrase deux."),
                "language": "fr",
            },
        )
        self.assertEqual(
            default_registry.evaluate(call).text, "Phrase une. Phrase deux."
        )

    def test_renderer_maps_a_qid_to_the_new_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "impl.json"
            path.write_text(
                json.dumps({"local:Q4200": "compose_ordered_paragraph"}),
                encoding="utf-8",
            )
            runtime = registry(path)
            call = FunctionCall(
                function_id="local:Q4200",
                arguments={
                    "parts": sentences("es", "Una.", "Dos."),
                    "language": "es",
                },
            )
            self.assertEqual(runtime.evaluate(call).text, "Una. Dos.")


if __name__ == "__main__":
    unittest.main()
