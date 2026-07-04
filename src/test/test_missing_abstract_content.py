import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.prepare_missing_content import (
    LANGUAGES,
    alternate_pages,
    content_token,
    write_partial_quickstatements,
    write_quickstatements,
)


class MissingAbstractContentTests(unittest.TestCase):
    def test_alternates_are_returned_in_supported_language_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            abstract = root / "Q315" / "index.html"
            abstract.parent.mkdir()
            links = []
            for language in reversed(LANGUAGES):
                page = root / language / "index.html"
                page.parent.mkdir()
                page.write_text("", encoding="utf-8")
                links.append(
                    f'<link rel="alternate" hreflang="{language}" '
                    f'href="../{language}/index.html">'
                )
            abstract.write_text("".join(links), encoding="utf-8")

            pages = alternate_pages(root, abstract)

            self.assertEqual(
                pages,
                [(root / language / "index.html").resolve() for language in LANGUAGES],
            )

    def test_quickstatements_deduplicate_repeated_content_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing.quickstatements"
            row = {
                "status": "missing-ready",
                "token": "M0001",
                **{language: f"{language} value" for language in LANGUAGES},
            }

            count = write_quickstatements(output, [row, dict(row)])
            text = output.read_text(encoding="utf-8")

            self.assertEqual(count, 1)
            self.assertEqual(text.count("CREATE"), 1)
            self.assertEqual(text.count("LAST|P40|"), len(LANGUAGES))

    def test_partial_quickstatements_keep_only_known_language_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.quickstatements"
            row = {
                "status": "missing-translations",
                "token": "M0002",
                **{language: "" for language in LANGUAGES},
            }
            row.update({"en": "Sentence.", "fr": "Phrase."})

            count = write_partial_quickstatements(output, [row])
            text = output.read_text(encoding="utf-8")

            self.assertEqual(count, 1)
            self.assertIn('LAST|P40|en:"Sentence."', text)
            self.assertIn('LAST|P40|fr:"Phrase."', text)
            self.assertNotIn("LAST|P40|ml:", text)

    def test_content_tokens_do_not_depend_on_inventory_order(self):
        values = tuple(f"{language} value" for language in LANGUAGES)

        self.assertEqual(content_token(values), content_token(values))
        self.assertNotEqual(
            content_token(values),
            content_token((*values[:-1], "changed")),
        )


if __name__ == "__main__":
    unittest.main()
