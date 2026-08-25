#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""A place label reads in the language of the page that shows it.

Places, unlike titles and personal names, are translated. A caption of the form
"<City>, <Country>" is a pure place label, so both halves belong to the page's
language: the French pages once read "Copenhague, Denmark", which is neither
French nor English.

Only labels whose halves are both in ``place-names.csv`` count. A descriptive
sentence that happens to end in a country name ("Flowers in Copenhagen,
Denmark") is a translation job, not a half-finished label, and translating only
its last word would leave two scripts in one sentence.
"""

import csv
import re
import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from languages import ORDER
from paths import REPO_ROOT

PLACE_NAMES = REPO_ROOT / "data/translations/place-names.csv"
ATTR = re.compile(r'\b(?:alt|title)="([^"]*)"')
CAPTION = re.compile(r"<(?:h\d|figcaption)\b[^>]*>\s*([^<]+?)\s*</(?:h\d|figcaption)>")


def _rows():
    with PLACE_NAMES.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _index(kind):
    found = {}
    for row in _rows():
        if row["kind"] != kind:
            continue
        for language in ORDER:
            if row[language]:
                found.setdefault(row[language], row)
    return found


CITY = _index("city")
COUNTRY = _index("country")


def mislabelled(language: str) -> list[tuple[str, str, str]]:
    """(page, label, expected) for every place label not in the page's language."""
    found = []
    for page in sorted((REPO_ROOT / language).glob("**/*.html")):
        text = page.read_text(encoding="utf-8", errors="replace")
        for value in ATTR.findall(text) + CAPTION.findall(text):
            if value.count(", ") != 1:
                continue
            head, tail = value.split(", ")
            city, country = CITY.get(head), COUNTRY.get(tail)
            if not (city and country):
                continue
            wanted = f"{city[language] or head}, {country[language] or tail}"
            if wanted != value:
                found.append((str(page.relative_to(REPO_ROOT)), value, wanted))
    return found


class PlaceLabelTests(unittest.TestCase):
    def test_every_place_label_reads_in_its_own_language(self):
        for language in ORDER:
            if language == "en":
                continue
            with self.subTest(language=language):
                wrong = mislabelled(language)
                self.assertEqual(
                    wrong, [], f"{len(wrong)} place label(s) in {language} are not translated"
                )

    def test_an_empty_cell_means_the_english_form(self):
        """The tables are sparse by design; a blank falls back to English.

        Most cities have no exonym outside the transliterating languages, so
        blanks are the normal case and must not be read as missing data.
        """
        blank = [row for row in _rows() if not row["fr"].strip()]
        self.assertTrue(blank, "expected sparse rows in place-names.csv")
        row = blank[0]
        self.assertEqual(row["fr"] or row["en"], row["en"])


if __name__ == "__main__":
    unittest.main()
