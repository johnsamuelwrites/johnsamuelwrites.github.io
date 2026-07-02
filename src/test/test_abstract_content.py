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


class TravelContentQuickStatementsTests(unittest.TestCase):
    def test_validator_accepts_complete_queryable_languages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "content.quickstatements"
            path.write_text(
                'CREATE\n'
                'LAST|Len|"Example"\n'
                'LAST|Lfr|"Exemple"\n'
                'LAST|Lml|"ഉദാഹരണം"\n'
                'LAST|Lpa|"ਉਦਾਹਰਨ"\n'
                'LAST|Lhi|"उदाहरण"\n'
                'LAST|Lpt|"Exemplo"\n'
                'LAST|Les|"Ejemplo"\n'
                'LAST|Lit|"Esempio"\n'
                'LAST|P40|en:"Example"\n'
                'LAST|P40|fr:"Exemple"\n'
                'LAST|P40|ml:"ഉദാഹരണം"\n'
                'LAST|P40|pa:"ਉਦਾਹਰਨ"\n'
                'LAST|P40|hi:"उदाहरण"\n'
                'LAST|P40|pt:"Exemplo"\n'
                'LAST|P40|es:"Ejemplo"\n'
                'LAST|P40|it:"Esempio"\n',
                encoding="utf-8",
            )

            self.assertEqual(validate_quickstatements(path), [])


if __name__ == "__main__":
    unittest.main()
