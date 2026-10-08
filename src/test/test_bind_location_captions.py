#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""A gallery caption is content: it must not reach a page as an English literal."""

import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "abstract"))

from abstract.bind_location_captions import (
    bind_text,
    captions,
    content_items_by_english,
    quickstatements,
)
from abstract.render_page import BINDABLE_ATTRIBUTES, SlotRewriter, template_slots
from abstract.validate_abstract_html import validate


CARDS = (
    '<ul>\n'
    '  <li><a data-location="Door" href="a.html"><img alt="" src="a.jpg" /></a></li>\n'
    '  <li><a data-location="Altar of the Chair of\n      Saint Peter" href="b.html"></a></li>\n'
    '</ul>\n'
)
FIRST = ("a", "", "", 0)
SECOND = ("a", "", "", 1)


class CaptionDiscoveryTests(unittest.TestCase):
    def test_captions_are_found_with_normalized_text(self):
        found = captions(CARDS)
        self.assertEqual(found[FIRST].value, "Door")
        self.assertEqual(found[SECOND].value, "Altar of the Chair of Saint Peter")

    def test_offsets_address_the_start_tag_across_lines(self):
        found = captions(CARDS)
        for caption in found.values():
            tag = CARDS[caption.start : caption.end]
            self.assertTrue(tag.startswith("<a ") and tag.endswith(">"), tag)


class BindTextTests(unittest.TestCase):
    def test_the_literal_is_replaced_by_the_bound_qid(self):
        text, count = bind_text(CARDS, {FIRST: "Q3365"})
        self.assertEqual(count, 1)
        self.assertIn(
            'data-content-data-location="local:Q3365" data-location="Q3365" href="a.html"',
            text,
        )
        self.assertNotIn('"Door"', text)
        self.assertIn("Saint Peter", text)

    def test_a_multi_line_caption_is_replaced_whole(self):
        text, _count = bind_text(CARDS, {SECOND: "Q9"})
        self.assertIn('data-location="Q9" href="b.html"', text)
        self.assertNotIn("Altar", text)

    def test_binding_twice_does_not_bind_twice(self):
        once, _ = bind_text(CARDS, {FIRST: "Q3365"})
        twice, count = bind_text(once, {FIRST: "Q1"})
        self.assertEqual(count, 0)
        self.assertEqual(once, twice)

    def test_the_rest_of_the_page_is_untouched(self):
        text, _ = bind_text(CARDS, {FIRST: "Q3365", SECOND: "Q9"})
        self.assertIn('<img alt="" src="a.jpg" />', text)
        self.assertEqual(text.count("<li>"), 2)


class QuickStatementsTests(unittest.TestCase):
    def test_only_complete_translation_rows_become_items(self):
        complete = {"en": "Bench", "fr": "Banc", "ml": "ബെഞ്ച്", "pa": "ਬੈਂਚ",
                    "hi": "बेंच", "pt": "Banco", "es": "Banco", "it": "Panchina"}
        partial = dict(complete, en="Bridge", it="")
        output, missing = quickstatements(["Bench", "Bridge"], {"bench": complete, "bridge": partial})
        self.assertEqual(output.count("CREATE"), 1)
        self.assertIn('LAST|Lit|"Panchina"', output)
        self.assertIn("LAST|P8|Q3185", output)
        self.assertEqual(missing, ["Bridge"])


class ContentItemLookupTests(unittest.TestCase):
    HEADER = "identifier,itemtype,en,fr,ml,pa,hi,pt,es,it\n"
    ROWS = (
        "Q10,Q3185,Sunset,Coucher du soleil — Sunset,x — Sunset,x — Sunset,x — Sunset,x — Sunset,x — Sunset,x — Sunset\n"
        "Q20,Q3185,Sunset,Coucher de soleil,a,b,c,Pôr do sol,Atardecer,Tramonto\n"
        "Q30,Q3185,Night,Night,Night,Night,Night,Night,Night,Night\n"
        "Q40,Q5,Door,Porte,a,b,c,Porta,Puerta,Porta\n"
    )

    def lookup(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "labels-wikibase.csv").write_text(self.HEADER + self.ROWS, encoding="utf-8")
            return content_items_by_english(Path(directory), **kwargs)

    def test_the_cleanly_translated_item_wins(self):
        self.assertEqual(self.lookup()["sunset"][0], "Q20")

    def test_an_untranslated_item_is_not_bound_but_offered_for_label_fixes(self):
        self.assertNotIn("night", self.lookup())
        self.assertEqual(self.lookup(untranslated=True)["night"], ["Q30"])

    def test_only_content_items_are_considered(self):
        self.assertNotIn("door", self.lookup())

    def test_an_untranslated_item_gets_label_fixes_not_a_new_item(self):
        texts = {"en": "Night", "fr": "Nuit", "ml": "രാത്രി", "pa": "ਰਾਤ",
                 "hi": "रात", "pt": "Noite", "es": "Noche", "it": "Notte"}
        output, missing = quickstatements(["Night"], {"night": texts}, {"night": ["Q30"]})
        self.assertNotIn("CREATE", output)
        self.assertIn('Q30|Lfr|"Nuit"', output)
        self.assertNotIn("Q30|Len", output)
        self.assertEqual(missing, [])


class RendererTests(unittest.TestCase):
    def test_data_location_is_bindable(self):
        self.assertIn("data-location", BINDABLE_ATTRIBUTES)

    def test_the_language_page_caption_is_rewritten(self):
        source = '<a data-location="Door" href="a.html"></a>'
        rewriter = SlotRewriter(source, {}, None, {(FIRST, "data-location"): "Porte"})
        self.assertEqual(rewriter.rewrite(), '<a data-location="Porte" href="a.html"></a>')

    def test_the_binding_is_discovered_on_the_abstract_page(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
            handle.write('<a data-content-data-location="local:Q3365" data-location="Q3365"></a>')
            path = Path(handle.name)
        try:
            _text, _counts, attributes = template_slots(path)
        finally:
            path.unlink()
        self.assertEqual(attributes, {(FIRST, "data-location"): "Q3365"})


class ValidatorTests(unittest.TestCase):
    HEAD = '<html lang="zxx" data-abstract-page="local:Q1" data-abstract-version="1">'

    def errors(self, body):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
            handle.write(f"{self.HEAD}{body}</html>")
            path = Path(handle.name)
        try:
            return validate(path)
        finally:
            path.unlink()

    def test_a_literal_caption_is_rejected(self):
        errors = self.errors('<a data-location="Door"></a>')
        self.assertEqual(len(errors), 1)
        self.assertIn("'Door'", errors[0])

    def test_a_bound_caption_is_accepted(self):
        self.assertEqual(
            self.errors('<a data-content-data-location="local:Q3365" data-location="Q3365"></a>'),
            [],
        )

    def test_a_caption_that_disagrees_with_its_binding_is_rejected(self):
        self.assertEqual(
            len(self.errors('<a data-content-data-location="local:Q3365" data-location="Q1"></a>')),
            1,
        )


if __name__ == "__main__":
    unittest.main()
