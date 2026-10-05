import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.localize_links import counterparts, localize_text

TRAVEL = {"en": "en/travel/index.html", "it": "it/viaggi/index.html"}
ABOUT = {"en": "en/about.html", "fr": "fr/apropos.html", "it": "it/chi-sono.html"}
GROUPS = counterparts([
    {f"target_{language}": path for language, path in group.items()}
    for group in (TRAVEL, ABOUT)
])
PAGE = "it/insegnamento/archivi.html"


def localize(text, page=PAGE, exists=lambda relative: True):
    return localize_text(text, page, GROUPS, exists)


class LocalizeLinksTests(unittest.TestCase):
    def test_rewrites_link_to_same_language_counterpart(self):
        text, changes = localize(
            '<a href="../../en/travel/index.html" property="item">Viaggio</a>'
        )
        self.assertEqual(
            text, '<a href="../viaggi/index.html" property="item">Viaggio</a>'
        )
        self.assertEqual(changes, [("../../en/travel/index.html", "../viaggi/index.html")])

    def test_keeps_fragment_and_query(self):
        text, _ = localize('<a href="../../en/about.html?x=1#cv">John</a>')
        self.assertIn('href="../chi-sono.html?x=1#cv"', text)

    def test_leaves_link_without_counterpart(self):
        source = '<a href="../../en/slides/2025/talk.html">Talk</a>'
        self.assertEqual(localize(source), (source, []))

    def test_leaves_link_when_counterpart_file_is_missing(self):
        source = '<a href="../../en/travel/index.html">Viaggio</a>'
        self.assertEqual(localize(source, exists=lambda relative: False), (source, []))

    def test_leaves_same_language_links(self):
        source = '<a href="../viaggi/index.html">Viaggio</a>'
        self.assertEqual(localize(source), (source, []))

    def test_hreflang_or_lang_marks_a_deliberate_language_link(self):
        for attribute in ('hreflang="en"', 'lang="en"'):
            source = f'<a href="../../en/travel/index.html" {attribute}>English</a>'
            self.assertEqual(localize(source), (source, []))

    def test_schema_in_language_marks_a_language_link(self):
        source = (
            '<a href="../../en/travel/index.html" property="url">'
            '<span property="inLanguage">English</span></a>'
        )
        self.assertEqual(localize(source), (source, []))

    def test_language_switcher_variants_are_left_alone(self):
        for opening, closing in (
            ('<div class="lang-selector">', "</div>"),
            ('<ul class="language-selector">', "</ul>"),
            ('<nav class="language-switcher">', "</nav>"),
            ('<ul id="langlist">', "</ul>"),
        ):
            source = f'{opening}<a href="../../en/travel/index.html">EN</a>{closing}'
            self.assertEqual(localize(source), (source, []))

    def test_english_page_links_back_to_english(self):
        text, _ = localize(
            '<a href="../../it/viaggi/index.html">Travel</a>', page="en/teaching/a.html"
        )
        self.assertIn('href="../travel/index.html"', text)

    def test_pages_outside_language_trees_are_untouched(self):
        source = '<a href="../en/travel/index.html">Travel</a>'
        self.assertEqual(localize(source, page="Q315/Q3062.html"), (source, []))

    def test_external_and_absolute_links_are_untouched(self):
        for href in ("https://example.org/en/travel/index.html", "/en/travel/index.html"):
            source = f'<a href="{href}">x</a>'
            self.assertEqual(localize(source), (source, []))


if __name__ == "__main__":
    unittest.main()
