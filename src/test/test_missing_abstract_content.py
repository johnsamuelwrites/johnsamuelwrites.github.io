import sys
import tempfile
import unittest
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.prepare_missing_content import (
    LANGUAGES,
    alternate_pages,
    best_candidate,
    content_token,
    fill_translations,
    load_translations,
    write_label_updates,
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
            self.assertIn('LAST|Len|"M0001 abstract content"', text)

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

    def test_reconciled_imports_get_real_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "labels.quickstatements"
            row = {
                "status": "existing-import-token",
                "token": "M0003",
                "qid": "Q9000",
                **{language: f"{language} value" for language in LANGUAGES},
            }

            count = write_label_updates(output, [row, dict(row)])
            text = output.read_text(encoding="utf-8")

            self.assertEqual(count, 1)
            self.assertIn('Q9000|Len|"en value"', text)
            self.assertEqual(text.count("Q9000|L"), len(LANGUAGES))

    def test_native_label_pages_are_not_translated(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "labels.quickstatements"
            row = {
                "status": "existing-import-token",
                "token": "M0004",
                "qid": "Q9100",
                "native_labels": "1",
                **{language: f"{language} value" for language in LANGUAGES},
            }

            count = write_label_updates(output, [row])
            text = output.read_text(encoding="utf-8")

            self.assertEqual(count, 1)
            # Every language reuses the authoritative English label verbatim.
            self.assertEqual(text.count('|"en value"'), len(LANGUAGES))
            self.assertNotIn("fr value", text)
            # Proper names carry no translated P40 statement, added or removed.
            self.assertNotIn("P40", text)

    def test_content_tokens_do_not_depend_on_inventory_order(self):
        values = tuple(f"{language} value" for language in LANGUAGES)

        self.assertEqual(content_token(values), content_token(values))
        self.assertNotEqual(
            content_token(values),
            content_token((*values[:-1], "changed")),
        )

    def test_reviewed_translations_fill_only_missing_values(self):
        values = ("English", "Français", "", "", "", "", "", "")
        filled = fill_translations(
            values,
            {
                "en": "must not overwrite",
                "ml": "മലയാളം",
                "hi": "हिन्दी",
            },
        )

        self.assertEqual(filled[0], "English")
        self.assertEqual(filled[2], "മലയാളം")
        self.assertEqual(filled[4], "हिन्दी")

    def test_translation_file_is_long_format_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translations.csv"
            with path.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.DictWriter(
                    destination, fieldnames=("token", "language", "text")
                )
                writer.writeheader()
                writer.writerow(
                    {"token": "M0123456789AB", "language": "pa", "text": "ਪੰਜਾਬੀ"}
                )
                writer.writerow(
                    {"token": "invalid", "language": "fr", "text": "ignored"}
                )

            self.assertEqual(
                load_translations(path),
                {"M0123456789AB": {"pa": "ਪੰਜਾਬੀ"}},
            )

    def test_candidate_requires_unique_multilingual_corroboration(self):
        values = ("Skip to main content", "Aller au contenu principal")
        exported = {
            "Q1": ("Skip to main content", "Skip to main content"),
            "Q2": ("Skip to main content", "Aller au contenu principal"),
        }

        self.assertEqual(best_candidate(["Q1", "Q2"], values, exported), "Q2")
        self.assertEqual(best_candidate(["Q1", "Q2"], values[:1], exported), "")
        self.assertEqual(
            best_candidate(
                ["Q1", "Q3"],
                ("Skip to main content",),
                {
                    "Q1": ("Skip to main content", ""),
                    "Q3": ("Skip to main content", "Texte complet"),
                },
            ),
            "Q3",
        )


if __name__ == "__main__":
    unittest.main()
