"""Attendance lists must run from the latest event to the earliest."""

import csv
import re
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
MONTHS = (
    "January February March April May June July August September October November December"
).split()


def start_date(text, year):
    """Read the start of the English CV's displayed date, including ranges."""
    text = " ".join(text.split())
    month = re.search(r"\b(" + "|".join(MONTHS) + r")\b", text)
    if month is None:
        raise ValueError(f"Attendance entry has no month: {text}")
    before = re.search(
        r"(?<!\d)(\d{1,2})(?:\s*[-–]\s*\d{1,2})?"
        r"(?:\s*(?:st|nd|rd|th))?\s*$",
        text[:month.start()],
    )
    after = re.match(r"\s+(\d{1,2})(?!\d)", text[month.end():])
    day = int((before or after)[1]) if before or after else 0
    return int(year), MONTHS.index(month[1]) + 1, day


class AttendanceOrderTests(unittest.TestCase):
    def test_every_detailed_cv_year_is_descending(self):
        soup = BeautifulSoup(
            (ROOT / "en/research/cv-detailed.html").read_text(), "html.parser"
        )
        years = []
        dates = []
        for node in soup.find("section", id="participation").find_all(
            ["h4", "p"], recursive=False
        ):
            if node.name == "h4":
                year = node.get_text(strip=True)
                years.append(int(year))
            else:
                dates.append(start_date(node.get_text(" ", strip=True), year))
        self.assertEqual(years, sorted(years, reverse=True))
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_composed_attendance_order_matches_in_every_view_and_language(self):
        with (ROOT / "data/content-updates/cv.csv").open() as source:
            rows = [r for r in csv.DictReader(source) if r["section"] == "participation"]
        expected = [
            r["local_qid"]
            for r in sorted(
                rows, key=lambda r: start_date(r["content"], r["year"]), reverse=True
            )
        ]
        with (ROOT / "src/main/abstract/content-migration-registry.csv").open() as source:
            pages = [r for r in csv.DictReader(source) if r["page_qid"] in ("Q3636", "Q3646")]
        for page in pages:
            paths = [page["abstract_path"]] + [
                page["target_" + language]
                for language in ("en", "fr", "ml", "pa", "hi", "pt", "es", "it")
            ]
            for path in paths:
                with self.subTest(path=path):
                    soup = BeautifulSoup((ROOT / path).read_text(), "html.parser")
                    actual = []
                    for node in soup.find_all("p"):
                        qid = (node.get("data-content") or node.get("data-q315-source") or "").removeprefix("local:")
                        if qid in expected:
                            actual.append(qid)
                    self.assertEqual(actual, expected)

    def test_range_start_and_month_precision(self):
        self.assertEqual(start_date("November 30-December 2, 2023", 2023), (2023, 11, 30))
        self.assertEqual(start_date("14-17 October, 2014", 2014), (2014, 10, 14))
        self.assertEqual(start_date("July 2026", 2026), (2026, 7, 0))


if __name__ == "__main__":
    unittest.main()
