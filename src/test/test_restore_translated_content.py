#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The counterpart of the untranslatable-names normalizer, in reverse."""

import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "abstract"))

import restore_translated_content as restore


def entity(labels=None, p40=None):
    return {
        "labels": {
            language: {"language": language, "value": value}
            for language, value in (labels or {}).items()
        },
        "claims": {
            "P40": [
                {
                    "id": f"Q1$statement-{language}",
                    "mainsnak": {
                        "datavalue": {
                            "value": {"language": language, "text": value},
                            "type": "monolingualtext",
                        }
                    },
                }
                for language, value in (p40 or {}).items()
            ]
        },
    }


ENGLISH = "All content maintained with care."
FRENCH = "Tout le contenu est maintenu avec soin."


class FlattenedLanguageTests(unittest.TestCase):
    def test_a_language_repeating_the_english_is_restored(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH}, p40={"en": ENGLISH, "fr": ENGLISH})
        found = restore.flattened_languages(item, {"en": ENGLISH, "fr": FRENCH})
        self.assertEqual(found, {"fr": FRENCH})

    def test_a_genuine_translation_is_never_overwritten(self):
        item = entity(labels={"en": ENGLISH, "fr": "Une autre traduction."},
                      p40={"en": ENGLISH, "fr": "Une autre traduction."})
        self.assertEqual(restore.flattened_languages(item, {"en": ENGLISH, "fr": FRENCH}), {})

    def test_a_placeholder_english_label_does_not_hide_a_flattened_p40(self):
        # Q4653's English label is an internal placeholder while P40 holds the prose.
        item = entity(
            labels={"en": "M27DF4F7F9C39 abstract sentence", "fr": ENGLISH},
            p40={"en": ENGLISH, "fr": ENGLISH},
        )
        self.assertEqual(
            restore.flattened_languages(item, {"en": ENGLISH, "fr": FRENCH}), {"fr": FRENCH}
        )

    def test_a_flattened_label_over_translated_p40_is_still_caught(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH}, p40={"en": ENGLISH, "fr": FRENCH})
        self.assertEqual(
            restore.flattened_languages(item, {"en": ENGLISH, "fr": FRENCH}), {"fr": FRENCH}
        )

    def test_a_repository_row_that_only_repeats_the_english_is_ignored(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH}, p40={"en": ENGLISH, "fr": ENGLISH})
        self.assertEqual(restore.flattened_languages(item, {"en": ENGLISH, "fr": ENGLISH}), {})

    def test_english_is_never_restored(self):
        item = entity(labels={"en": ENGLISH}, p40={"en": ENGLISH})
        self.assertNotIn("en", restore.flattened_languages(item, {"en": FRENCH, "fr": FRENCH}))


class CorrectionTests(unittest.TestCase):
    def test_p40_is_replaced_in_place_keeping_its_statement_id(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH}, p40={"en": ENGLISH, "fr": ENGLISH})
        data = restore.corrections(item, {"fr": FRENCH})
        self.assertEqual(len(data["claims"]), 1)
        self.assertEqual(data["claims"][0]["id"], "Q1$statement-fr")
        self.assertEqual(
            data["claims"][0]["mainsnak"]["datavalue"]["value"]["text"], FRENCH
        )

    def test_only_the_named_languages_are_touched(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH, "it": ENGLISH},
                      p40={"en": ENGLISH, "fr": ENGLISH, "it": ENGLISH})
        data = restore.corrections(item, {"fr": FRENCH})
        self.assertEqual(sorted(data["labels"]), ["fr"])
        self.assertEqual(
            [c["mainsnak"]["datavalue"]["value"]["language"] for c in data["claims"]], ["fr"]
        )

    def test_an_item_already_correct_yields_no_edit(self):
        item = entity(labels={"en": ENGLISH, "fr": FRENCH}, p40={"en": ENGLISH, "fr": FRENCH})
        self.assertEqual(restore.corrections(item, {"fr": FRENCH}), {})

    def test_the_original_entity_is_not_mutated(self):
        item = entity(labels={"en": ENGLISH, "fr": ENGLISH}, p40={"en": ENGLISH, "fr": ENGLISH})
        restore.corrections(item, {"fr": FRENCH})
        self.assertEqual(
            item["claims"]["P40"][1]["mainsnak"]["datavalue"]["value"]["text"], ENGLISH
        )


if __name__ == "__main__":
    unittest.main()
