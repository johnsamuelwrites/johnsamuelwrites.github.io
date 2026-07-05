"""Tests for the direct Wikibase import/export helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from wikibase_write import build_data, datavalue, load_env, parse, split_line


class WikibaseWriterTests(unittest.TestCase):
    def test_split_line_preserves_pipes_inside_quoted_values(self):
        self.assertEqual(
            split_line('Q1|Len|"one | two"'),
            ["Q1", "Len", "one | two"],
        )

    def test_parse_groups_create_and_last_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.quickstatements"
            source.write_text(
                'CREATE\nLAST|Len|"New item"\nLAST|P8|Q2\n'
                'Q1|Lfr|"Existant"\n',
                encoding="utf-8",
            )
            operations = parse(source)
        self.assertEqual(len(operations), 2)
        self.assertIsNone(operations[0].subject)
        self.assertEqual(operations[1].subject, "Q1")

    def test_builds_terms_and_typed_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.quickstatements"
            source.write_text(
                'CREATE\nLAST|Len|"New item"\nLAST|P8|Q2\n'
                'LAST|P40|fr:"Bonjour"\n',
                encoding="utf-8",
            )
            operation = parse(source)[0]
        data = build_data(
            operation, {"P8": "wikibase-item", "P40": "monolingualtext"}
        )
        self.assertEqual(data["labels"]["en"]["value"], "New item")
        self.assertEqual(
            data["claims"]["P8"][0]["mainsnak"]["datavalue"]["value"]["id"],
            "Q2",
        )
        self.assertEqual(
            data["claims"]["P40"][0]["mainsnak"]["datavalue"]["value"],
            {"language": "fr", "text": "Bonjour"},
        )

    def test_rejects_wrong_item_value(self):
        with self.assertRaises(ValueError):
            datavalue("not-an-item", "wikibase-item")

    def test_load_env_does_not_replace_process_secret(self):
        import os

        original = os.environ.get("WIKIBASE_USERNAME")
        os.environ["WIKIBASE_USERNAME"] = "from-process"
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / ".env"
                source.write_text(
                    'WIKIBASE_USERNAME="from-file"\nTEST_BOT_VALUE=loaded\n',
                    encoding="utf-8",
                )
                source.chmod(0o600)
                load_env(source)
            self.assertEqual(os.environ["WIKIBASE_USERNAME"], "from-process")
            self.assertEqual(os.environ.pop("TEST_BOT_VALUE"), "loaded")
        finally:
            if original is None:
                os.environ.pop("WIKIBASE_USERNAME", None)
            else:
                os.environ["WIKIBASE_USERNAME"] = original

    def test_load_env_rejects_public_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / ".env"
            source.write_text("WIKIBASE_PASSWORD=secret\n", encoding="utf-8")
            source.chmod(0o644)
            with self.assertRaises(PermissionError):
                load_env(source)


if __name__ == "__main__":
    unittest.main()
