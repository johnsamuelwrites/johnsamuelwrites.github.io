#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Stored content must not carry the escaping of the format it passed through."""

import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "abstract"))

from abstract.css_assets import DEFAULT_DATA_DIR
from abstract.repair_escaped_quotes import corrections, damaged, load_labels
from languages import ORDER


def row(**values):
    base = {language: "" for language in ORDER}
    base.update(values)
    return base


class DamageDetectionTests(unittest.TestCase):
    def test_an_escaped_quote_is_repaired(self):
        found = damaged({"Q1": row(en='\\"Salvator Mundi\\" and after')})
        self.assertEqual(found["Q1"]["en"], '"Salvator Mundi" and after')

    def test_clean_text_is_left_alone(self):
        self.assertEqual(damaged({"Q1": row(en='"Salvator Mundi"')}), {})

    def test_leaked_markup_is_not_treated_as_an_escaping_artifact(self):
        """Unescaping Q4013's French would have left it just as broken."""
        found = damaged({"Q1": row(fr='traiter certaines de href=\\"./index.html\\">mes photos')})
        self.assertEqual(found, {})

    def test_each_damaged_language_is_reported_separately(self):
        found = damaged({"Q1": row(en='a \\"b\\"', fr="propre", ml='c \\"d\\"')})
        self.assertEqual(sorted(found["Q1"]), ["en", "ml"])


class CorrectionTests(unittest.TestCase):
    @staticmethod
    def entity(labels, p40):
        return {
            "labels": {k: {"language": k, "value": v} for k, v in labels.items()},
            "claims": {
                "P40": [
                    {
                        "id": f"Q1$s-{k}",
                        "mainsnak": {"datavalue": {"value": {"language": k, "text": v}}},
                    }
                    for k, v in p40.items()
                ]
            },
        }

    def test_both_stores_are_written(self):
        entity = self.entity({"en": '\\"x\\"'}, {"en": '\\"x\\"'})
        data = corrections(entity, {"en": '"x"'})
        self.assertEqual(data["labels"]["en"]["value"], '"x"')
        self.assertEqual(data["claims"][0]["mainsnak"]["datavalue"]["value"]["text"], '"x"')

    def test_p40_keeps_its_statement_id(self):
        entity = self.entity({"en": '\\"x\\"'}, {"en": '\\"x\\"'})
        self.assertEqual(corrections(entity, {"en": '"x"'})["claims"][0]["id"], "Q1$s-en")

    def test_an_already_clean_item_yields_no_edit(self):
        entity = self.entity({"en": '"x"'}, {"en": '"x"'})
        self.assertEqual(corrections(entity, {"en": '"x"'}), {})

    def test_the_entity_passed_in_is_not_mutated(self):
        entity = self.entity({"en": '\\"x\\"'}, {"en": '\\"x\\"'})
        corrections(entity, {"en": '"x"'})
        self.assertEqual(
            entity["claims"]["P40"][0]["mainsnak"]["datavalue"]["value"]["text"], '\\"x\\"'
        )


class SnapshotTests(unittest.TestCase):
    def test_no_stored_value_carries_an_escaped_quote(self):
        """Regression guard: the repaired items must stay repaired."""
        remaining = damaged(load_labels(DEFAULT_DATA_DIR))
        self.assertEqual(
            sorted(remaining)[:5], [], f"{len(remaining)} item(s) still escaped"
        )


if __name__ == "__main__":
    unittest.main()
