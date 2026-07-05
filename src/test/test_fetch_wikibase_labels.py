import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.fetch_wikibase_labels import _Bound, existing_identifiers


class FetchWikibaseLabelsTests(unittest.TestCase):
    def test_bound_parser_collects_content_and_entity_qids(self):
        parser = _Bound()
        parser.feed(
            '<p data-content="local:Q10">x</p>'
            '<a data-entity="local:Q20">y</a>'
            '<span data-content="wikidata:Q30">z</span>'  # not local: ignored
            '<span>plain</span>'
        )
        self.assertEqual(parser.qids, {"Q10", "Q20"})

    def test_existing_identifiers_reads_valid_qids(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with (data / "labels-wikibase.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("identifier", "itemtype", "en"))
                writer.writeheader()
                writer.writerow({"identifier": "Q5", "itemtype": "Q3185", "en": "a"})
                writer.writerow({"identifier": "P8", "itemtype": "", "en": "prop"})
                writer.writerow({"identifier": "", "itemtype": "", "en": "blank"})

            self.assertEqual(existing_identifiers(data), {"Q5"})

    def test_existing_identifiers_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(existing_identifiers(Path(directory)), set())


if __name__ == "__main__":
    unittest.main()
