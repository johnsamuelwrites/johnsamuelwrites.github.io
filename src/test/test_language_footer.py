import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.normalize_language_footer import (
    css_ready,
    normalize,
    render_selector,
)
from abstract.verify_language_footer import FooterParser, verify_page


GROUP = {
    "en": "en/teaching/index.html",
    "fr": "fr/enseignement/index.html",
    "it": "it/insegnamento/index.html",
}

DUAL_FOOTER = """<!doctype html><html><body>
  <footer>
   <nav aria-label="Language versions" class="language-switcher">
    <ul class="language-switcher-list">
     <li><a class="language-link" href="../../en/teaching/index.html">English</a></li>
     <li><a class="language-link" href="../../fr/enseignement/index.html">Français</a></li>
    </ul>
   </nav>
   <div class="footer-content">
    <div class="footer-lang">
     <div class="lang-selector">
      <a class="lang-btn active" href="../../en/teaching/index.html">English</a>
      <a class="lang-btn" href="../../fr/enseignement/index.html">Français</a>
     </div>
    </div>
    <p>© 2025 John Samuel</p>
   </div>
  </footer>
</body></html>
"""


def _write(directory: Path, relative: str, text: str) -> Path:
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


LANGLIST_FOOTER = """<!doctype html><html><body>
  <footer>
   <ul class="language-grid" id="langlist">
    <li class="highlight" id="enpage"><span lang="en"><a class="langlink"
       href="../../en/teaching/index.html"><span>English</span></a></span></li>
    <li id="frpage"><span lang="fr"><a class="langlink"
       href="../../fr/enseignement/index.html"><span>Français</span></a></span></li>
    <li id="itpage"><span lang="it"><a class="langlink"
       href="../../it/insegnamento/index.html"><span>Italiano</span></a></span></li>
   </ul>
  </footer>
</body></html>
"""


class FooterParserTests(unittest.TestCase):
    def test_collects_selector_and_basic_nav(self):
        parser = FooterParser()
        parser.feed(DUAL_FOOTER)
        # The basic nav plus the styled lang-selector are two switchers.
        self.assertEqual(parser.language_switcher_count, 1)
        self.assertEqual(len(parser.switchers), 1)
        buttons = parser.switchers[0]
        self.assertEqual(len(buttons), 2)
        self.assertEqual([button.active for button in buttons], [True, False])

    def test_langlist_form_is_a_switcher(self):
        parser = FooterParser()
        parser.feed(LANGLIST_FOOTER)
        self.assertEqual(parser.language_switcher_count, 0)
        self.assertEqual(len(parser.switchers), 1)
        links = parser.switchers[0]
        self.assertEqual([link.language for link in links], ["en", "fr", "it"])
        self.assertEqual([link.active for link in links], [True, False, False])


class NormalizeTests(unittest.TestCase):
    def test_expands_selector_and_drops_legacy_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in GROUP.values():
                _write(root, relative, DUAL_FOOTER)
            page = root / "it/insegnamento/index.html"
            text, changed = normalize(root, page, "it", GROUP)

            self.assertTrue(changed)
            self.assertNotIn("language-switcher", text)
            # One button per group language, current language active.
            self.assertEqual(text.count('class="lang-btn"'), 2)
            self.assertEqual(text.count('class="lang-btn active"'), 1)
            self.assertIn('class="lang-btn active" href="index.html"', text)
            # Copyright content is preserved.
            self.assertIn("John Samuel", text)

    def test_normalized_page_passes_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for language, relative in GROUP.items():
                page = _write(root, relative, DUAL_FOOTER)
                text, _ = normalize(root, page, language, GROUP)
                page.write_text(text, encoding="utf-8")
            for language, relative in GROUP.items():
                result = verify_page(root, relative, language, GROUP)
                self.assertEqual(result.errors, [], f"{relative}: {result.errors}")

    def test_render_selector_self_link_is_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = _write(root, "it/insegnamento/index.html", "")
            selector = render_selector(root, page, "it", GROUP, "     ")
            self.assertIn('href="index.html"', selector)
            self.assertIn('href="../../en/teaching/index.html"', selector)


class VerifierTests(unittest.TestCase):
    def test_flags_legacy_nav_and_missing_and_wrong_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in GROUP.values():
                _write(root, relative, DUAL_FOOTER)
            # Unmodified page: english active but current is italian, missing it button.
            result = verify_page(root, "it/insegnamento/index.html", "it", GROUP)
            joined = " | ".join(result.errors)
            self.assertIn("language-switcher", joined)
            self.assertIn("missing link for [it]", joined)
            self.assertIn("not the current language page", joined)

    def test_accepts_valid_langlist_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # LANGLIST_FOOTER highlights english, so it is correct for en.
            _write(root, "en/teaching/index.html", LANGLIST_FOOTER)
            result = verify_page(root, "en/teaching/index.html", "en", dict(GROUP))
            self.assertEqual(result.errors, [])


class CssReadyTests(unittest.TestCase):
    def test_reads_linked_stylesheet_regardless_of_attr_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "assets/site.css", ".lang-selector{} .lang-btn{} .lang-btn.active{}")
            page = _write(
                root,
                "en/page.html",
                '<link data-x="1" href="../assets/site.css" rel="stylesheet"/>',
            )
            self.assertTrue(css_ready(root, page))

    def test_missing_rules_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = _write(root, "en/page.html", "<style>.foo{}</style>")
            self.assertFalse(css_ready(root, page))


if __name__ == "__main__":
    unittest.main()
