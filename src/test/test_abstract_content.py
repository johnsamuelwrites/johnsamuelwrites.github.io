import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.functions.registry import (
    CONCATENATE_BOOTSTRAP_KEY,
    default_registry,
)
from abstract.model import FunctionCall, MonolingualText
from abstract.prepare_q3062_hero import (
    abstract_markup,
    bind,
    load_pilot,
    missing_translations,
    item_tokens,
    property_tokens,
    quickstatements,
    structural_quickstatements,
    validate_bindings,
)
from abstract.prepare_travel_content import validate_quickstatements
from abstract.validate_abstract_html import validate


class AbstractFunctionTests(unittest.TestCase):
    def test_concatenate_preserves_language_and_order(self):
        result = default_registry.evaluate(
            FunctionCall(
                function_id=CONCATENATE_BOOTSTRAP_KEY,
                arguments={
                    "parts": [
                        MonolingualText("en", "First."),
                        MonolingualText("en", "Second."),
                    ],
                    "language": "en",
                },
            )
        )

        self.assertEqual(result, MonolingualText("en", "First. Second."))

    def test_concatenate_rejects_mixed_languages(self):
        with self.assertRaises(ValueError):
            default_registry.evaluate(
                FunctionCall(
                    function_id=CONCATENATE_BOOTSTRAP_KEY,
                    arguments={
                        "parts": [
                            MonolingualText("en", "Hello."),
                            MonolingualText("fr", "Bonjour."),
                        ],
                        "language": "en",
                    },
                )
            )

    def test_unknown_function_is_rejected(self):
        with self.assertRaises(ValueError):
            default_registry.evaluate(FunctionCall("local:Q999999", {}))


class AbstractHTMLValidatorTests(unittest.TestCase):
    def validate_text(self, html):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.html"
            path.write_text(html, encoding="utf-8")
            return validate(path)

    def test_valid_function_markup(self):
        errors = self.validate_text(
            '<html lang="zxx" data-abstract-page="local:Q1" '
            'data-abstract-version="1"><q-call data-function="local:Q2">'
            '<q-arg data-name="parts"><span data-content="local:Q3">'
            "Q3</span></q-arg></q-call></html>"
        )
        self.assertEqual(errors, [])

    def test_unqualified_qids_are_rejected(self):
        errors = self.validate_text(
            '<html lang="zxx" data-abstract-page="Q1" '
            'data-abstract-version="1"><span data-entity="Q2"></span></html>'
        )
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("qualified" in error for error in errors))

    def test_argument_outside_call_is_rejected(self):
        errors = self.validate_text(
            '<html lang="zxx" data-abstract-page="local:Q1" '
            'data-abstract-version="1"><q-arg data-name="parts">'
            "</q-arg></html>"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("contained in q-call", errors[0])


class Q3062PilotTests(unittest.TestCase):
    PILOT = (
        Path(__file__).resolve().parents[1]
        / "main"
        / "abstract"
        / "pilots"
        / "Q3062-hero.json"
    )

    def test_pilot_contains_all_required_translations(self):
        missing = missing_translations(load_pilot(self.PILOT))

        for languages in missing.values():
            self.assertEqual(languages, [])

    def test_quickstatements_create_function_paragraph_and_sentences(self):
        output = quickstatements(load_pilot(self.PILOT))

        self.assertEqual(output.count("CREATE"), 8)
        self.assertIn('LAST|Len|"abstract paragraph"', output)
        self.assertIn('LAST|Len|"abstract sentence"', output)
        self.assertIn('LAST|Len|"concatenate monolingual text"', output)
        self.assertEqual(output.count("LAST|Len|"), 8)
        for language in ("fr", "ml", "pa", "hi", "pt", "es", "it"):
            self.assertEqual(output.count(f"LAST|L{language}|"), 3)

    def test_quickstatements_skip_items_with_real_bindings(self):
        pilot = load_pilot(self.PILOT)
        output = quickstatements(
            pilot,
            bindings={
                "ABSTRACT_FUNCTION_CLASS": "Q3834",
                "ABSTRACT_PARAGRAPH_CLASS": "Q3835",
                "ABSTRACT_SENTENCE_CLASS": "Q3836",
                "CONCATENATE_MONOLINGUAL_TEXT": "Q3837",
            },
        )

        self.assertEqual(output.count("CREATE"), 4)
        self.assertNotIn('LAST|Len|"abstract function"', output)
        self.assertNotIn('LAST|Len|"concatenate monolingual text"', output)
        self.assertIn('LAST|Len|"Q3062 hero description"', output)

    def test_quickstatements_are_empty_when_every_item_is_bound(self):
        pilot = load_pilot(self.PILOT)
        bindings = {
            token: f"Q{index}"
            for index, token in enumerate(item_tokens(pilot), 100)
        }

        self.assertEqual(quickstatements(pilot, bindings), "")

    def test_bindings_require_distinct_real_qids(self):
        pilot = load_pilot(self.PILOT)
        tokens = item_tokens(pilot)
        bindings = {token: f"Q{index}" for index, token in enumerate(tokens, 1)}
        bindings.update(
            {
                token: f"P{index}"
                for index, token in enumerate(property_tokens(pilot), 40)
            }
        )

        self.assertEqual(validate_bindings(pilot, bindings), [])
        bindings[tokens[-1]] = bindings[tokens[0]]
        self.assertTrue(validate_bindings(pilot, bindings))

    def test_missing_bindings_do_not_report_false_duplicates(self):
        pilot = load_pilot(self.PILOT)

        errors = validate_bindings(pilot, {})

        self.assertFalse(
            any("distinct QID" in error for error in errors),
            errors,
        )

    def test_structural_statements_are_typed_ordered_and_queryable(self):
        pilot = load_pilot(self.PILOT)
        bindings = {
            token: f"Q{index}"
            for index, token in enumerate(item_tokens(pilot), 100)
        }
        bindings.update(
            {
                token: f"P{index}"
                for index, token in enumerate(property_tokens(pilot), 40)
            }
        )

        output = structural_quickstatements(pilot, bindings)

        self.assertIn("Q104|P8|Q101", output)
        self.assertIn("Q105|P8|Q102", output)
        self.assertIn("Q104|P21|Q3062", output)
        self.assertIn("Q104|P41|Q103", output)
        self.assertIn('Q105|P21|Q104|P42|"1"', output)
        self.assertIn('Q105|P40|ml:"', output)

    def test_abstract_markup_uses_only_bound_qids(self):
        pilot = load_pilot(self.PILOT)
        tokens = [
            pilot["function_token"],
            pilot["paragraph_token"],
            *(part["token"] for part in pilot["parts"]),
        ]
        bindings = {token: f"Q{index}" for index, token in enumerate(tokens, 10)}

        markup = abstract_markup(pilot, bindings, "  ")

        self.assertIn('data-function="local:Q10"', markup)
        self.assertIn('data-content="local:Q11"', markup)
        self.assertIn(">Q12</span>", markup)
        self.assertNotIn("Q3062_HERO_", markup)

    def test_bind_refuses_to_change_page_while_a_qid_is_missing(self):
        pilot = load_pilot(self.PILOT)
        tokens = [
            pilot["function_token"],
            pilot["paragraph_token"],
            *(part["token"] for part in pilot["parts"]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings_path = root / "bindings.csv"
            bindings_path.write_text(
                "token,qid\n"
                + "".join(
                    f"{token},{'' if index == 10 else f'Q{index}'}\n"
                    for index, token in enumerate(tokens, 10)
                ),
                encoding="utf-8",
            )
            page = root / "page.html"
            original = (
                '<html lang="zxx" data-abstract-page="local:Q3062" '
                'data-abstract-version="1"><p class="hero-description">'
                "Current text.</p></html>"
            )
            page.write_text(original, encoding="utf-8")

            result = bind(self.PILOT, bindings_path, page)

            self.assertEqual(result, 1)
            self.assertEqual(page.read_text(encoding="utf-8"), original)


class TravelContentQuickStatementsTests(unittest.TestCase):
    QUICKSTATEMENTS = (
        Path(__file__).resolve().parents[1]
        / "main"
        / "abstract"
        / "travel-content.quickstatements"
    )

    def test_generated_travel_content_has_complete_queryable_languages(self):
        self.assertEqual(validate_quickstatements(self.QUICKSTATEMENTS), [])


if __name__ == "__main__":
    unittest.main()
