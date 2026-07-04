import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.functions.text import compose_ordered_paragraph
from abstract.prepare_abstract_composition import (
    COMPOSE_FUNCTION_TOKEN,
    is_prose,
    plan,
    segment,
    structure_quickstatements,
)
from abstract.prepare_travel_content import LANGUAGES
from abstract.wikibase_resolver import WikibaseResolver

TWO_SENTENCES = {
    "en": "I started photography years back. My father inspired me.",
    "fr": "J'ai commencé la photographie il y a des années. Mon père m'a inspiré.",
    "ml": "ഞാൻ വർഷങ്ങൾക്ക് മുമ്പ് ഫോട്ടോഗ്രാഫി തുടങ്ങി. എന്റെ പിതാവ് എന്നെ പ്രചോദിപ്പിച്ചു.",
    "pa": "ਮੈਂ ਸਾਲ ਪਹਿਲਾਂ ਫੋਟੋਗ੍ਰਾਫੀ ਸ਼ੁਰੂ ਕੀਤੀ। ਮੇਰੇ ਪਿਤਾ ਨੇ ਮੈਨੂੰ ਪ੍ਰੇਰਿਤ ਕੀਤਾ।",
    "hi": "मैंने साल पहले फोटोग्राफी शुरू की। मेरे पिता ने मुझे प्रेरित किया।",
    "pt": "Comecei a fotografar há anos. O meu pai inspirou-me.",
    "es": "Empecé la fotografía hace años. Mi padre me inspiró.",
    "it": "Ho iniziato a fotografare anni fa. Mio padre mi ha ispirato.",
}


class SegmentationTests(unittest.TestCase):
    def test_prose_is_detected_by_terminal_punctuation(self):
        self.assertTrue(is_prose("A full sentence."))
        self.assertTrue(is_prose("What is it?"))
        self.assertFalse(is_prose("Architecture"))
        # A name whose only dots are internal abbreviations is not prose.
        self.assertFalse(is_prose("A. R. Rahman"))
        self.assertFalse(is_prose("H.G. Wells"))

    def test_aligned_languages_split_into_matching_sentences(self):
        values = tuple(TWO_SENTENCES[language] for language in LANGUAGES)
        parts = segment(values)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0][0], "I started photography years back.")
        self.assertEqual(parts[1][0], "My father inspired me.")

    def test_a_count_mismatch_falls_back_to_one_sentence(self):
        # English has two sentences; Spanish has one. The tuple must stay whole.
        values = tuple(
            "One. Two." if language == "en" else "Una sola frase sin division"
            for language in LANGUAGES
        )
        self.assertEqual(len(segment(values)), 1)


class PipelineTests(unittest.TestCase):
    def _build(self, root: Path) -> None:
        alternates = "".join(
            f'<link rel="alternate" hreflang="{language}" href="../../{language}/p.html">'
            for language in LANGUAGES
        )
        (root / "Q315" / "Q10").mkdir(parents=True)
        (root / "Q315" / "Q10" / "index.html").write_text(
            '<html lang="zxx" data-abstract-page="local:Q10" data-abstract-version="1">'
            f'<head>{alternates}</head><body><p class="lead">LEAD</p></body></html>',
            encoding="utf-8",
        )
        for language in LANGUAGES:
            page = root / language / "p.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(
                f'<html><body><p class="lead">{TWO_SENTENCES[language]}</p></body></html>',
                encoding="utf-8",
            )

    def test_prose_slot_becomes_a_two_sentence_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._build(root)
            compositions, sentence_values, slot_rows = plan(
                root, [("Q10", Path("Q315/Q10/index.html"))]
            )
            self.assertEqual(len(compositions), 1)
            self.assertEqual(len(compositions[0].sentences), 2)
            self.assertEqual(len(sentence_values), 2)
            self.assertEqual(len(slot_rows), 1)

    def test_composition_round_trips_through_resolver_and_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._build(root)
            compositions, _, _ = plan(root, [("Q10", Path("Q315/Q10/index.html"))])
            composition = compositions[0]

            # Assign real-looking QIDs and materialise a Wikibase snapshot,
            # exactly as an import + reconciliation would produce.
            function = "Q9000"
            paragraph = "Q9001"
            sentence_qids = {
                token: f"Q90{index:02d}"
                for index, (token, _) in enumerate(composition.sentences, 10)
            }
            entities = {
                function: {"claims": {"P8": [_item("Q3834")]}},
                "Q3834": {"claims": {"P8": []}},
                "Q3835": {"claims": {"P8": []}},
                "Q3836": {"claims": {"P8": []}},
                paragraph: {
                    "claims": {
                        "P8": [_item("Q3835")],
                        "P41": [_item(function)],
                    }
                },
            }
            for ordinal, (token, values) in enumerate(composition.sentences, 1):
                entities[sentence_qids[token]] = {
                    "claims": {
                        "P8": [_item("Q3836")],
                        "P21": [
                            {
                                "mainsnak": {"datavalue": {"value": {"id": paragraph}}},
                                "qualifiers": {"P42": [{"datavalue": {"value": str(ordinal)}}]},
                            }
                        ],
                        "P40": [
                            {"mainsnak": {"datavalue": {"value": {"language": language, "text": text}}}}
                            for language, text in zip(LANGUAGES, values)
                            if text
                        ],
                    }
                }

            resolver = WikibaseResolver({"schema_version": 1, "entities": entities})
            resolved = resolver.paragraph(paragraph)
            for language in LANGUAGES:
                call = resolver.call(resolved, language)
                composed = compose_ordered_paragraph(**call.arguments)
                self.assertEqual(composed.text, TWO_SENTENCES[language])

    def test_structure_statements_link_paragraph_and_sentences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._build(root)
            compositions, _, slot_rows = plan(
                root, [("Q10", Path("Q315/Q10/index.html"))]
            )
            composition = compositions[0]
            bindings = {COMPOSE_FUNCTION_TOKEN: "Q9000", composition.token: "Q9001"}
            rows = [{"kind": "paragraph", "token": composition.token, "parent_token": "", "ordinal": ""}]
            for ordinal, (token, _) in enumerate(composition.sentences, 1):
                bindings[token] = f"Q90{ordinal:02d}"
                rows.append(
                    {
                        "kind": "sentence",
                        "token": token,
                        "parent_token": composition.token,
                        "ordinal": str(ordinal),
                    }
                )
            resolved = {composition.token}
            output = structure_quickstatements(rows, slot_rows, bindings, resolved)
            self.assertIn("Q9001|P41|Q9000", output)
            self.assertIn("Q9001|P21|Q10", output)
            self.assertIn('Q9001|P42|"1"', output)


def _item(qid):
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}


if __name__ == "__main__":
    unittest.main()
