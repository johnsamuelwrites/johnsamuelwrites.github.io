import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

import io
import json
from unittest import mock

from abstract import fetch_wikibase_labels
import datetime
from abstract.fetch_wikibase_labels import (
    _Bound,
    changed_items,
    existing_identifiers,
    items_created_after,
    last_fetch,
    state_path,
    truncated,
)


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


    def test_items_created_after_the_export_are_listed_across_pages(self):
        """A just-imported item is neither exported nor bound, yet must be fetched."""
        pages = [
            {"query": {"allpages": [{"title": "Item:Q9"}, {"title": "Item:Q10021"}]},
             "continue": {"apcontinue": "Q2", "continue": "-||"}},
            {"query": {"allpages": [{"title": "Item:Q9997"}, {"title": "Item:Q9994"}]}},
        ]
        responses = iter(io.BytesIO(json.dumps(page).encode()) for page in pages)
        with mock.patch.object(fetch_wikibase_labels.urllib.request, "urlopen",
                               side_effect=lambda *a, **k: next(responses)):
            self.assertEqual(items_created_after(9994, pause=0), {"Q9997", "Q10021"})


    def test_a_label_is_only_replaced_when_p40_continues_it(self):
        long_text = "A very long description " + "x" * 300
        self.assertTrue(truncated(long_text[:247] + "...", long_text))
        # A label that ends in an ellipsis on purpose keeps its translation.
        self.assertFalse(truncated("10+ lieux • Paris, Lyon...", "10+ Locations • Paris, Lyon..."))
        self.assertFalse(truncated("Bench", "Bench"))


    def test_an_incremental_run_asks_only_for_items_changed_since_the_last(self):
        pages = [
            {"query": {"recentchanges": [{"title": "Item:Q8670"}, {"title": "Property:P40"}]},
             "continue": {"rccontinue": "x", "continue": "-||"}},
            {"query": {"recentchanges": [{"title": "Item:Q10071"}]}},
        ]
        requests = []

        def respond(request, *args, **kwargs):
            requests.append(request.full_url)
            return io.BytesIO(json.dumps(pages[len(requests) - 1]).encode())

        since = datetime.datetime(2026, 10, 9, 9, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.object(fetch_wikibase_labels.urllib.request, "urlopen", side_effect=respond):
            self.assertEqual(changed_items(since, pause=0), {"Q8670", "Q10071"})
        self.assertIn("rcstart=2026-10-09T09%3A00%3A00Z", requests[0])

    def test_the_last_fetch_time_is_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory, "labels-wikibase.csv")
            self.assertIsNone(last_fetch(out))
            out.write_text("identifier\n", encoding="utf-8")
            state_path(out).write_text('{"fetched_at": "2026-10-09T09:54:01+00:00"}', encoding="utf-8")
            self.assertEqual(last_fetch(out).hour, 9)


if __name__ == "__main__":
    unittest.main()
