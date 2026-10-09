#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""An abstract page must not carry natural-language text where a QID belongs."""

import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from abstract.verify_abstract_literals import displayed_attributes, literals

PROSE = {"alt", "title", "aria-label", "placeholder", "data-location"}


def found(body, prose=PROSE):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
        handle.write(f'<html lang="zxx"><body>{body}</body></html>')
        path = Path(handle.name)
    try:
        return [text for _line, _where, text in literals(path, prose)]
    finally:
        path.unlink()


class LiteralTextTests(unittest.TestCase):
    def test_qids_are_not_literals(self):
        self.assertEqual(found("<h4>Q3155</h4><p>Q3970 • Q3971</p>"), [])

    def test_english_text_is_a_literal(self):
        self.assertEqual(found("<div class='stat-label'>Cities</div>"), ["Cities"])

    def test_numbers_and_symbols_alone_are_not_literals(self):
        self.assertEqual(found("<span>2026</span><span>•</span><span>404</span>"), [])

    def test_the_language_switcher_names_are_allowed(self):
        self.assertEqual(found("<a>English</a><a>Français</a><a>മലയാളം</a>"), [])

    def test_scripts_styles_and_function_calls_are_skipped(self):
        body = (
            "<script>const label = 'Search';</script><style>p::after{content:'x'}</style>"
            "<q-call data-function='local:Q1'><q-arg data-name='x'>words</q-arg></q-call>"
        )
        self.assertEqual(found(body), [])

    def test_text_after_a_void_element_is_still_checked(self):
        self.assertEqual(found("<p>Q1<br>About Me</p>"), ["About Me"])


class LiteralAttributeTests(unittest.TestCase):
    def test_the_gallery_caption_bug_is_caught(self):
        """The case that shipped "Door" to every language page."""
        self.assertEqual(found('<a data-location="Door" href="x.html"></a>'), ["Door"])

    def test_a_bound_caption_is_not_a_literal(self):
        self.assertEqual(
            found('<a data-content-data-location="local:Q3365" data-location="Q3365"></a>'), []
        )

    def test_an_empty_alt_is_not_a_literal(self):
        self.assertEqual(found('<img alt="" src="x.jpg" />'), [])

    def test_urls_and_classes_are_not_prose(self):
        self.assertEqual(found('<a class="photo card" href="Q3062/Q3018.html"></a>'), [])

    def test_attributes_shown_through_css_are_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            css = Path(directory, "page.css")
            css.write_text(".card::after { content: attr(data-city); }\n.x { width: 2px }", encoding="utf-8")
            self.assertEqual(displayed_attributes([css]), {"data-city"})

    def test_a_discovered_attribute_is_checked(self):
        self.assertEqual(found('<a data-city="Church"></a>', PROSE | {"data-city"}), ["Church"])
        self.assertEqual(found('<a data-city="Church"></a>'), [])


if __name__ == "__main__":
    unittest.main()
