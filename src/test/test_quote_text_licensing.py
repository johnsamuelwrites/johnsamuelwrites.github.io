#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Copyrighted quotations render from the repository, never from the Wikibase."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.local_text import LOCAL_TEXT_ITEMTYPE, local_text, overlay
from abstract.quote_text_licensing import (
    BLANKED_DESCRIPTION,
    METADATA_ONLY_DESCRIPTION,
    blank_edit,
    QUOTES_PAGE_URL,
    metadata_only_edit,
    public_domain_edit,
)
from abstract.render_page import COMPOSED_ITEMTYPES
from content_update import (
    ContentRow,
    ContentUpdateError,
    content_text_for_wikibase,
    refuse_metadata_only_write,
)

HEADER = "quote,attribution,local_qid,attribution_qid,text_in_wikibase\n"


def quotes_csv(body: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    handle.write(HEADER + body)
    handle.close()
    return Path(handle.name)


def quote_row(text_in_wikibase: str) -> ContentRow:
    return ContentRow(
        family="quotes",
        row_number=2,
        data={
            "type": "Quote",
            "category": "Art",
            "quote": "Some words.",
            "attribution": "An Author",
            "local_qid": "Q1",
            "attribution_qid": "Q2",
            "text_in_wikibase": text_in_wikibase,
        },
    )


class LocalTextTests(unittest.TestCase):
    def test_only_rows_marked_no_are_held_locally(self):
        path = quotes_csv('"Kept, here.",A,Q1,Q2,no\nPublic domain.,B,Q3,Q4,\n')
        self.assertEqual(set(local_text(path)), {"Q1"})

    def test_text_is_the_original_in_every_language_with_whitespace_collapsed(self):
        path = quotes_csv('"Two\n      lines.",A,Q1,Q2,no\n')
        texts = local_text(path)["Q1"]
        self.assertEqual(set(texts.values()), {"Two lines."})
        self.assertIn("ml", texts)

    def test_overlay_replaces_the_descriptive_label_and_makes_the_item_atomic(self):
        path = quotes_csv("Some words.,A,Q1,Q2,no\n")
        labels = {"Q1": {"identifier": "Q1", "itemtype": "Q3835", "en": "Quotation by A"}}
        row = overlay(labels, path)["Q1"]
        self.assertEqual(row["en"], "Some words.")
        self.assertEqual(row["itemtype"], LOCAL_TEXT_ITEMTYPE)
        self.assertNotIn(row["itemtype"], COMPOSED_ITEMTYPES)

    def test_overlay_supplies_items_the_mirror_does_not_have(self):
        path = quotes_csv("Some words.,A,Q9,Q2,no\n")
        self.assertEqual(overlay({}, path)["Q9"]["fr"], "Some words.")

    def test_the_repository_holds_the_three_copyrighted_quotations(self):
        self.assertEqual(set(local_text()), {"Q6319", "Q4304", "Q4305"})


class ContentUpdateGuardTests(unittest.TestCase):
    def test_metadata_only_rows_get_a_descriptive_wikibase_name(self):
        self.assertEqual(content_text_for_wikibase(quote_row("no")), "Quotation by An Author")
        self.assertEqual(content_text_for_wikibase(quote_row("")), "Some words.")

    def test_writing_text_for_a_metadata_only_row_is_refused(self):
        with self.assertRaises(ContentUpdateError):
            refuse_metadata_only_write(quote_row("no"))
        refuse_metadata_only_write(quote_row(""))


def claim(prop, value, claim_id):
    if isinstance(value, str) and value.startswith("Q"):
        datavalue = {"value": {"id": value}, "type": "wikibase-entityid"}
    else:
        datavalue = {"value": value}
    return {"id": claim_id, "mainsnak": {"property": prop, "datavalue": datavalue}}


class MetadataOnlyEditTests(unittest.TestCase):
    ROW = {"local_qid": "Q4304", "attribution": "Isaac Asimov", "attribution_qid": "Q6323"}

    def test_text_and_constructor_are_removed_and_metadata_added(self):
        entity = {
            "labels": {"en": {"value": "M3A516F589529 abstract paragraph"}},
            "claims": {
                "P8": [claim("P8", "Q3835", "s1")],
                "P41": [claim("P41", "Q4182", "s2")],
                "P40": [claim("P40", {"language": "en", "text": "words"}, "s3")],
                "P21": [claim("P21", "Q3639", "s4")],
            },
        }
        data = metadata_only_edit(entity, self.ROW)
        removed = {change["id"] for change in data["claims"] if "remove" in change}
        self.assertEqual(removed, {"s1", "s2", "s3"})
        added = {
            change["mainsnak"]["property"]: change["mainsnak"]["datavalue"]["value"]
            for change in data["claims"]
            if "remove" not in change
        }
        self.assertEqual(added["P8"]["id"], "Q3185")
        self.assertEqual(added["P15"]["id"], "Q6323")
        self.assertEqual(added["P3"], QUOTES_PAGE_URL)
        self.assertEqual(data["labels"]["en"]["value"], "Quotation by Isaac Asimov")
        self.assertEqual(data["labels"]["fr"]["value"], "Citation : Isaac Asimov")
        self.assertEqual(data["descriptions"]["en"]["value"], METADATA_ONLY_DESCRIPTION)

    def test_an_item_already_in_shape_needs_nothing(self):
        entity = {"claims": {}, "labels": {}, "descriptions": {}}
        done = metadata_only_edit(entity, self.ROW)
        entity = {
            "labels": done["labels"],
            "descriptions": done["descriptions"],
            "claims": {
                "P8": [claim("P8", "Q3185", "a")],
                "P15": [claim("P15", "Q6323", "b")],
                "P3": [claim("P3", QUOTES_PAGE_URL, "c")],
            },
        }
        self.assertEqual(metadata_only_edit(entity, self.ROW), {})


class PublicDomainEditTests(unittest.TestCase):
    def test_p40_is_replaced_in_place(self):
        entity = {
            "labels": {"en": {"value": "old"}},
            "claims": {"P40": [claim("P40", {"language": "en", "text": "old"}, "s1")]},
        }
        data = public_domain_edit(entity, "new")
        self.assertEqual(data["claims"][0]["id"], "s1")
        self.assertEqual(data["claims"][0]["mainsnak"]["datavalue"]["value"]["text"], "new")
        self.assertEqual(data["labels"]["en"]["value"], "new")


class BlankEditTests(unittest.TestCase):
    def test_text_type_and_membership_are_stripped(self):
        entity = {
            "labels": {"en": {"value": "words"}, "fr": {"value": "words"}},
            "descriptions": {"en": {"value": "sentence"}},
            "claims": {
                "P40": [claim("P40", {"language": "en", "text": "words"}, "s1")],
                "P21": [claim("P21", "Q4304", "s2")],
                "P8": [claim("P8", "Q3836", "s3")],
            },
        }
        data = blank_edit(entity)
        self.assertEqual({change["id"] for change in data["claims"]}, {"s1", "s2", "s3"})
        self.assertTrue(all("remove" in label for label in data["labels"].values()))
        self.assertEqual(data["descriptions"]["en"]["value"], BLANKED_DESCRIPTION)

    def test_a_blanked_item_needs_nothing(self):
        entity = {"labels": {}, "descriptions": {"en": {"value": BLANKED_DESCRIPTION}}, "claims": {}}
        self.assertEqual(blank_edit(entity), {})


if __name__ == "__main__":
    unittest.main()
