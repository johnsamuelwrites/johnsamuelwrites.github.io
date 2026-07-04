import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.prepare_content_corrections import (
    classify,
    typographic_variant,
    write_quickstatements,
)
from abstract.prepare_travel_content import LANGUAGES

# Each entry is (css_class, qid); the abstract page binds the class to the QID
# and every language page carries the same class so the slot keys align.
SLOTS = [
    ("typo", "Q100"),
    ("offby", "Q200"),
    ("absent", "Q300"),
    ("degr", "Q400"),
    ("unal", "Q500"),
    ("wbmiss", "Q600"),
]

LABELS = (
    "identifier,itemtype,en,fr,ml,pa,hi,pt,es,it\n"
    "Q100,Q3185,Search,Recherche,tr,tr,tr,tr,Buscar,tr\n"
    "Q200,Q3185,Home,Accueil,tr,tr,tr,tr,Inicio,tr\n"
    "Q300,Q3185,About,APropos,ml300,tr,tr,tr,Acerca,tr\n"
    "Q400,Q3185,Flowers,Fleurs,tr,tr,tr,tr,Café,tr\n"
    "Q500,Q3185,Contact,Contact,tr,tr,tr,tr,Contacto,tr\n"
    "Q600,Q3185,Blog,,tr,tr,tr,tr,Blogue,tr\n"
)

# Per-language rendered text for each slot class. Empty string omits the slot.
PAGE_TEXT = {
    "en": {"typo": "Search", "offby": "Home", "absent": "About",
           "degr": "Flowers", "unal": "WRONG", "wbmiss": "Blog"},
    "fr": {"typo": "Recherche", "offby": "Bonjour", "absent": "APropos",
           "degr": "Fleurs", "unal": "Contact", "wbmiss": "Blogue"},
    "es": {"typo": "buscar", "offby": "Inicio", "absent": "Acerca",
           "degr": "Caf?", "unal": "Contacto", "wbmiss": "Blog"},
}


def language_page(language: str) -> str:
    text = PAGE_TEXT.get(language, {})
    spans = "".join(
        f'<span class="{css}">{text[css]}</span>'
        for css, _ in SLOTS
        if text.get(css)
    )
    return f'<html lang="{language}"><body>{spans}</body></html>'


def abstract_page() -> str:
    alternates = "".join(
        f'<link rel="alternate" hreflang="{language}" href="../../{language}/p.html">'
        for language in LANGUAGES
    )
    spans = "".join(
        f'<span class="{css}" data-content="local:{qid}">{qid}</span>'
        for css, qid in SLOTS
    )
    return (
        '<html lang="zxx" data-abstract-page="local:Q10" data-abstract-version="1">'
        f"<head>{alternates}</head><body>{spans}</body></html>"
    )


class TypographicVariantTests(unittest.TestCase):
    def test_case_and_accent_differences_are_variants(self):
        self.assertTrue(typographic_variant("buscar", "Buscar"))
        self.assertTrue(typographic_variant("Séries", "series"))

    def test_different_words_are_not_variants(self):
        self.assertFalse(typographic_variant("Bonjour", "Accueil"))
        self.assertFalse(typographic_variant("", "Buscar"))


class CorrectionsTests(unittest.TestCase):
    def _build(self, root: Path) -> Path:
        data = root / "data"
        data.mkdir()
        (data / "labels-wikibase.csv").write_text(LABELS, encoding="utf-8")
        (root / "Q315" / "Q10").mkdir(parents=True)
        (root / "Q315" / "Q10" / "index.html").write_text(
            abstract_page(), encoding="utf-8"
        )
        for language in LANGUAGES:
            page = root / language / "p.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(language_page(language), encoding="utf-8")
        return data

    def test_classification_and_safe_quickstatements(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self._build(root)
            sources = [("Q10", Path("Q315/Q10/index.html"))]
            rows = classify(root, data, sources)

            def status(qid, language):
                return next(
                    row["status"]
                    for row in rows
                    if row["qid"] == qid and row["language"] == language
                )

            self.assertEqual(status("Q100", "es"), "differs")   # buscar vs Buscar
            self.assertEqual(status("Q100", "fr"), "match")
            self.assertEqual(status("Q200", "fr"), "differs")   # Bonjour vs Accueil
            self.assertEqual(status("Q300", "ml"), "page-absent")
            self.assertEqual(status("Q400", "es"), "page-degraded")
            self.assertEqual(status("Q600", "fr"), "wikibase-missing")

            output = root / "content-corrections.quickstatements"
            write_quickstatements(output, rows)
            text = output.read_text(encoding="utf-8")

            # Emitted: the typographic correction and the genuine addition.
            self.assertIn('Q100|Les|"buscar"', text)
            self.assertIn('Q600|Lfr|"Blogue"', text)
            self.assertIn('Q600|P40|fr:"Blogue"', text)

            # Never emitted: occurrence drift, missing slots, page corruption,
            # unaligned slots, or an untranslated English echo (Q600 ml).
            self.assertNotIn("Q200", text)   # different word
            self.assertNotIn("Q300", text)   # page-absent
            self.assertNotIn("Q400", text)   # page-degraded
            self.assertNotIn("Q500", text)   # unaligned (en mismatch)
            self.assertNotIn("Q600|Lml", text)  # untranslated echo


if __name__ == "__main__":
    unittest.main()
