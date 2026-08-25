#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.normalize_untranslatable_names import (
    COMPOSED_ITEMTYPES,
    EXCLUDED,
    LANGUAGES,
    canonical_values,
    composed_qids,
    corrections,
    english_value,
    split_quote_parts,
    write_with_retry,
)

from wikibase_api import WikibaseError


def entity(labels: dict[str, str], p40: dict[str, str]) -> dict:
    return {
        "labels": {l: {"language": l, "value": v} for l, v in labels.items()},
        "claims": {
            "P40": [
                {
                    "id": f"Q1$claim-{language}",
                    "type": "statement",
                    "rank": "normal",
                    "mainsnak": {
                        "snaktype": "value",
                        "property": "P40",
                        "datatype": "monolingualtext",
                        "datavalue": {
                            "type": "monolingualtext",
                            "value": {"language": language, "text": text},
                        },
                    },
                }
                for language, text in p40.items()
            ]
        },
    }


class CorrectionTests(unittest.TestCase):
    def test_translated_labels_are_reset(self):
        data = corrections(
            entity({"en": "Steven Pinker", "ml": "സ്റ്റീവൻ പിങ്കർ"}, {}),
            "Steven Pinker",
        )
        self.assertEqual(data["labels"]["ml"]["value"], "Steven Pinker")
        self.assertNotIn("en", data["labels"])

    def test_every_language_is_covered_even_when_absent(self):
        data = corrections(entity({"en": "Queen"}, {}), "Queen")
        self.assertEqual(set(data["labels"]), set(LANGUAGES) - {"en"})

    def test_p40_is_replaced_in_place(self):
        data = corrections(
            entity({}, {"en": "The Grand Design", "fr": "Le grand dessein"}),
            "The Grand Design",
        )
        self.assertEqual(len(data["claims"]), 1)
        claim = data["claims"][0]
        self.assertEqual(claim["id"], "Q1$claim-fr")
        self.assertEqual(claim["mainsnak"]["datavalue"]["value"]["text"], "The Grand Design")
        self.assertEqual(claim["mainsnak"]["datavalue"]["value"]["language"], "fr")

    def test_an_already_canonical_item_needs_no_edit(self):
        canonical = {l: "Yo-Yo Ma" for l in LANGUAGES}
        self.assertEqual(corrections(entity(canonical, canonical), "Yo-Yo Ma"), {})

    def test_a_long_title_truncates_the_label_but_not_the_content(self):
        long_title = "A " + "very " * 80 + "long title"
        data = corrections(entity({"en": "x"}, {"en": "x"}), long_title)
        self.assertLessEqual(len(data["labels"]["en"]["value"]), 250)
        self.assertTrue(data["labels"]["en"]["value"].endswith("..."))
        self.assertEqual(data["claims"][0]["mainsnak"]["datavalue"]["value"]["text"], long_title)

    def test_other_properties_are_untouched(self):
        item = entity({"en": "Queen"}, {"fr": "Reine"})
        item["claims"]["P4"] = [{"id": "Q1$other"}]
        data = corrections(item, "Queen")
        self.assertTrue(all(c["mainsnak"]["property"] == "P40" for c in data["claims"]))


class CanonicalValueTests(unittest.TestCase):
    def setUp(self):
        self.values, self.conflicts = canonical_values()

    def test_the_csvs_agree_on_every_value(self):
        self.assertEqual(self.conflicts, [])

    def test_shared_items_are_excluded(self):
        # Q3900 is both a book title and a place whose translation is correct.
        self.assertIn("Q3900", EXCLUDED)
        for qid in EXCLUDED:
            self.assertNotIn(qid, self.values)

    def test_values_lose_the_indentation_carried_over_from_html(self):
        self.assertFalse(any("\n" in v or "  " in v for v in self.values.values()))

    def test_titles_authors_and_attributions_are_all_covered(self):
        self.assertGreater(len(self.values), 1000)
        self.assertEqual(self.values.get("Q7434"), "Queen")


class SplitQuoteTests(unittest.TestCase):
    """A split quote's text lives in its parts, not in the composed wrapper."""

    def test_composed_wrappers_are_not_given_the_whole_quote(self):
        values, _ = canonical_values()
        for qid in composed_qids() & set(values):
            self.fail(f"composed item {qid} was given a canonical value")

    def test_parts_are_collected_from_the_csv(self):
        parts = split_quote_parts()
        self.assertIn("Q4642", parts)
        self.assertGreater(len(parts), 10)

    def test_a_part_takes_its_english_p40_as_canonical(self):
        item = entity({"en": "a label"}, {"en": "the original text", "fr": "le texte"})
        self.assertEqual(english_value(item), "the original text")

    def test_a_part_falls_back_to_its_english_label(self):
        self.assertEqual(english_value(entity({"en": "only a label"}, {})), "only a label")

    def test_a_part_with_no_english_value_yields_nothing(self):
        self.assertEqual(english_value(entity({"fr": "seulement"}, {})), "")

    def test_plain_quote_items_are_covered(self):
        values, _ = canonical_values()
        # Q6319 is an unsplit quote, so its text is the CSV value.
        self.assertEqual(values.get("Q6319"), "Have no fear of perfection — you'll never reach it.")


class FakeClient:
    """Records writes and fails them on demand, without touching the network."""

    def __init__(self, failures):
        self.failures = list(failures)
        self.writes = 0
        self.logins = 0

    def edit_entity(self, data, entity_id=None, summary=None):
        if self.failures:
            raise WikibaseError(self.failures.pop(0))
        self.writes += 1
        return {}

    def login(self, username, password):
        self.logins += 1


class RetryTests(unittest.TestCase):
    """A run of this length hits both the edit throttle and session expiry."""

    def setUp(self):
        patcher = mock.patch("time.sleep", lambda _s: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(
            "os.environ", {"WIKIBASE_USERNAME": "u", "WIKIBASE_PASSWORD": "p"}
        )
        env.start()
        self.addCleanup(env.stop)

    def test_a_clean_write_needs_no_retry(self):
        client = FakeClient([])
        self.assertTrue(write_with_retry(client, "Q1", {}, "s"))
        self.assertEqual((client.writes, client.logins), (1, 0))

    def test_a_throttled_write_is_retried_without_signing_in(self):
        client = FakeClient(["failed-save: The save has failed."])
        self.assertTrue(write_with_retry(client, "Q1", {}, "s"))
        self.assertEqual((client.writes, client.logins), (1, 0))

    def test_an_expired_session_signs_in_again(self):
        client = FakeClient(["assertuserfailed: You are no longer logged in"])
        self.assertTrue(write_with_retry(client, "Q1", {}, "s"))
        self.assertEqual((client.writes, client.logins), (1, 1))

    def test_a_persistently_failing_item_is_skipped_not_fatal(self):
        client = FakeClient(["failed-save"] * 4)
        self.assertFalse(write_with_retry(client, "Q1", {}, "s"))
        self.assertEqual(client.writes, 0)


if __name__ == "__main__":
    unittest.main()
