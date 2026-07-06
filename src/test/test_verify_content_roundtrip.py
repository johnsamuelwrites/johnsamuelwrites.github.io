import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.verify_content_roundtrip import canonical_value


class CanonicalValueTests(unittest.TestCase):
    def test_decodes_quotes_escaped_by_the_wikibase_csv_export(self):
        self.assertEqual(
            canonical_value(r'\"Photography is a way of feeling.'),
            '"Photography is a way of feeling.',
        )

    def test_collapses_visible_whitespace(self):
        self.assertEqual(canonical_value("one\n  two"), "one two")


if __name__ == "__main__":
    unittest.main()
