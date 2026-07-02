import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.functions.registry import FunctionRegistry
from abstract.functions.text import concatenate_monolingual_text
from abstract.wikibase_resolver import WikibaseResolver


SNAPSHOT = {
    "schema_version": 1,
    "entities": {
        "Q3834": {"claims": {"P8": []}},
        "Q3835": {"claims": {"P8": []}},
        "Q3836": {"claims": {"P8": []}},
        "Q3837": {"claims": {"P8": [{"mainsnak": {"datavalue": {"value": {"id": "Q3834"}}}}]}},
        "Q3838": {
            "claims": {
                "P8": [{"mainsnak": {"datavalue": {"value": {"id": "Q3835"}}}}],
                "P41": [{"mainsnak": {"datavalue": {"value": {"id": "Q3837"}}}}],
            }
        },
        "Q3839": {
            "claims": {
                "P8": [{"mainsnak": {"datavalue": {"value": {"id": "Q3836"}}}}],
                "P21": [{
                    "mainsnak": {"datavalue": {"value": {"id": "Q3838"}}},
                    "qualifiers": {"P42": [{"datavalue": {"value": "1"}}]},
                }],
                "P40": [
                    {"mainsnak": {"datavalue": {"value": {"language": language, "text": text}}}}
                    for language, text in {
                        "en": "Heterogeneity defines my journey.",
                        "fr": "L'hétérogénéité définit mon parcours.",
                        "ml": "വൈവിധ്യമാണ് എന്റെ യാത്രയെ നിർവചിക്കുന്നത്.",
                        "pa": "ਵਿਭਿੰਨਤਾ ਮੇਰੀ ਯਾਤਰਾ ਨੂੰ ਪਰਿਭਾਸ਼ਿਤ ਕਰਦੀ ਹੈ।",
                        "hi": "विविधता मेरी यात्रा को परिभाषित करती है।",
                        "pt": "A heterogeneidade define o meu percurso.",
                        "es": "La heterogeneidad define mi recorrido.",
                        "it": "L'eterogeneità definisce il mio viaggio.",
                    }.items()
                ],
            }
        },
        "Q3840": {
            "claims": {
                "P8": [{"mainsnak": {"datavalue": {"value": {"id": "Q3836"}}}}],
                "P21": [{
                    "mainsnak": {"datavalue": {"value": {"id": "Q3838"}}},
                    "qualifiers": {"P42": [{"datavalue": {"value": "2"}}]},
                }],
                "P40": [
                    {"mainsnak": {"datavalue": {"value": {"language": language, "text": text}}}}
                    for language, text in {
                        "en": "Every photograph captures time.",
                        "fr": "Chaque photographie capture le temps.",
                        "ml": "ഓരോ ചിത്രവും സമയത്തെ പകർത്തുന്നു.",
                        "pa": "ਹਰ ਤਸਵੀਰ ਸਮੇਂ ਨੂੰ ਕੈਦ ਕਰਦੀ ਹੈ।",
                        "hi": "हर तस्वीर समय को कैद करती है।",
                        "pt": "Cada fotografia capta o tempo.",
                        "es": "Cada fotografía captura el tiempo.",
                        "it": "Ogni fotografia cattura il tempo.",
                    }.items()
                ],
            }
        },
        "Q3841": {
            "claims": {
                "P8": [{"mainsnak": {"datavalue": {"value": {"id": "Q3836"}}}}],
                "P21": [{
                    "mainsnak": {"datavalue": {"value": {"id": "Q3838"}}},
                    "qualifiers": {"P42": [{"datavalue": {"value": "3"}}]},
                }],
                "P40": [
                    {"mainsnak": {"datavalue": {"value": {"language": language, "text": text}}}}
                    for language, text in {
                        "en": "Join me across countries.",
                        "fr": "Rejoignez-moi à travers les pays.",
                        "ml": "രാജ്യങ്ങളിലൂടെയുള്ള യാത്രയിൽ എന്നോടൊപ്പം ചേരൂ.",
                        "pa": "ਦੇਸ਼ਾਂ ਵਿੱਚ ਮੇਰੇ ਨਾਲ ਜੁੜੋ।",
                        "hi": "देशों की यात्रा में मेरे साथ जुड़ें।",
                        "pt": "Junte-se a mim por diferentes países.",
                        "es": "Acompáñame por distintos países.",
                        "it": "Unisciti a me attraverso i paesi.",
                    }.items()
                ],
            }
        },
    },
}


class WikibaseResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = WikibaseResolver(SNAPSHOT)
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
        self.assertTrue(result.text.endswith("pays."))


if __name__ == "__main__":
    unittest.main()
