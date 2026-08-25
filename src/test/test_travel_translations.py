#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import csv
import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

import refresh_travel_pages as travel
from languages import ORDER


class CsvShapeTests(unittest.TestCase):
    def setUp(self):
        with travel.IMAGE_DESCRIPTIONS_CSV.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            self.fieldnames = reader.fieldnames
            self.rows = list(reader)

    def test_a_column_per_language(self):
        self.assertEqual(self.fieldnames, ["table", *ORDER])

    def test_every_row_is_complete(self):
        for row in self.rows:
            with self.subTest(en=row["en"]):
                self.assertIn(row["table"], {"alt", "caption"})
                self.assertTrue(row["en"].strip())
                for language in ORDER:
                    self.assertTrue(row[language].strip(), f"{row['en']!r} missing {language}")

    def test_english_keys_are_unique_within_a_table(self):
        for table in ("alt", "caption"):
            keys = [r["en"] for r in self.rows if r["table"] == table]
            with self.subTest(table=table):
                self.assertEqual(len(keys), len(set(keys)))

    def test_a_key_in_both_tables_agrees_with_itself(self):
        """translate_image_text reads alt first, so a disagreement would be silent."""
        alt = {r["en"]: r for r in self.rows if r["table"] == "alt"}
        for row in self.rows:
            if row["table"] == "caption" and row["en"] in alt:
                with self.subTest(en=row["en"]):
                    self.assertEqual(row, {**alt[row["en"]], "table": "caption"})


class LoaderTests(unittest.TestCase):
    def test_tables_are_loaded_and_keyed_by_english(self):
        alt, caption = travel.load_image_descriptions()
        self.assertEqual(alt, travel.PHOTO_ALT_TRANSLATIONS)
        self.assertEqual(caption, travel.PHOTO_CAPTION_TRANSLATIONS)
        self.assertIn("Abbey", caption)
        self.assertEqual(caption["Abbey"]["fr"], "Abbaye")

    def test_english_is_not_stored_as_a_translation(self):
        alt, caption = travel.load_image_descriptions()
        for table in (alt, caption):
            for values in table.values():
                self.assertNotIn("en", values)

    def test_an_unknown_table_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text(
                "table,en,fr,ml,pa,hi,pt,es,it\nsubtitle,A,B,C,D,E,F,G,H\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                travel.load_image_descriptions(path)


class TranslationTests(unittest.TestCase):
    def test_english_is_returned_unchanged(self):
        self.assertEqual(travel.translate_image_text("Abbey", "en"), "Abbey")

    def test_a_known_caption_is_translated(self):
        self.assertEqual(travel.translate_image_text("Abbey", "fr"), "Abbaye")
        self.assertEqual(travel.translate_image_text("Abbey", "it"), "Abbazia")

    def test_surrounding_whitespace_still_matches(self):
        self.assertEqual(travel.translate_image_text("  Abbey  ", "fr"), "Abbaye")

    def test_unknown_text_falls_back_to_the_original(self):
        self.assertEqual(travel.translate_image_text("Nothing here", "fr"), "Nothing here")

    def test_an_unsupported_language_falls_back_to_the_original(self):
        self.assertEqual(travel.translate_image_text("Abbey", "de"), "Abbey")

    def test_alt_text_is_translated_in_place(self):
        markup = '<img alt="Abbey" class="photo-image" />'
        self.assertIn("Abbaye", travel.translate_image_descriptions(markup, "fr"))
        self.assertEqual(travel.translate_image_descriptions(markup, "en"), markup)


class PlaceNameTests(unittest.TestCase):
    """Place names are genuinely translated, unlike the names in content-updates."""

    def setUp(self):
        self.countries, self.cities = travel.load_place_names()

    def test_countries_carry_every_language(self):
        for name, values in self.countries.items():
            with self.subTest(country=name):
                self.assertEqual(set(values), set(ORDER) - {"en"})

    def test_countries_use_real_exonyms(self):
        self.assertEqual(self.countries["Germany"]["fr"], "Allemagne")
        self.assertEqual(self.countries["Germany"]["it"], "Germania")
        self.assertEqual(self.countries["Spain"]["es"], "España")

    def test_every_city_is_transliterated_for_the_indic_scripts(self):
        """Those three write in their own script, so every city has an entry."""
        for name, values in self.cities.items():
            with self.subTest(city=name):
                self.assertTrue({"ml", "pa", "hi"} <= set(values))

    def test_latin_script_entries_are_exonyms_not_transliterations(self):
        """A Latin-script cell is filled only where the language has its own name."""
        filled = {
            language: sum(1 for v in self.cities.values() if v.get(language))
            for language in ("fr", "pt", "es", "it")
        }
        self.assertEqual(filled["fr"], 15)
        self.assertEqual(filled["pt"], 0)
        self.assertEqual(filled["es"], 0)
        self.assertEqual(filled["it"], 0)

    def test_an_empty_cell_means_the_english_form_is_used(self):
        self.assertIsNone(self.cities["Lyon"].get("fr"))
        self.assertEqual(travel.translated_city_name("Lyon", "fr"), "Lyon")
        self.assertNotEqual(travel.translated_city_name("Lyon", "ml"), "Lyon")

    def test_an_unknown_kind_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("kind,en,fr,ml,pa,hi,pt,es,it\nregion,A,B,C,D,E,F,G,H\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                travel.load_place_names(path)


class PageSlugTests(unittest.TestCase):
    def test_every_slug_has_every_language(self):
        for slug, values in travel.PAGE_SLUG_TRANSLATIONS.items():
            with self.subTest(slug=slug):
                self.assertEqual(set(values), set(ORDER) - {"en"})

    def test_slugs_are_url_safe(self):
        for slug, values in travel.PAGE_SLUG_TRANSLATIONS.items():
            for language, value in values.items():
                with self.subTest(slug=slug, language=language):
                    self.assertNotIn(" ", value)
                    self.assertNotIn("/", value)


class UiLabelTests(unittest.TestCase):
    def test_labels_are_keyed_by_language_then_key(self):
        labels = travel.load_ui_labels()
        self.assertEqual(set(labels), set(ORDER))
        # Completeness is asserted per key in SparseLabelTests: some labels exist
        # only in the languages that have their own wording for them.
        for language in ORDER:
            with self.subTest(language=language):
                self.assertTrue(labels[language])

    def test_a_known_label_is_translated(self):
        labels = travel.load_ui_labels()
        self.assertEqual(labels["en"]["photography"], "Photography")
        self.assertEqual(labels["fr"]["photography"], "Photographie")


class NoInlineVocabularyTests(unittest.TestCase):
    def test_the_travel_vocabulary_is_no_longer_in_python(self):
        """Guard against a dictionary creeping back into the module."""
        source = (MAIN / "refresh_travel_pages.py").read_text(encoding="utf-8")
        for name in (
            "PHOTO_ALT_TRANSLATIONS",
            "PHOTO_CAPTION_TRANSLATIONS",
            "CITY_NAME_TRANSLATIONS",
            "COUNTRY_NAME_TRANSLATIONS",
            "PAGE_SLUG_TRANSLATIONS",
            "COUNTRY_PAGE_LABELS",
            "TRAVEL_DIRS",
            "TRAVEL_INDEX_DIRS",
            "SITE_TAGLINES",
            "FOOTER_TITLES",
            "HIGHLIGHTS",
            "FRENCH_CITY_FILENAME_OVERRIDES",
        ):
            with self.subTest(table=name):
                self.assertNotIn(f"{name} = {{", source)


class PathSegmentTests(unittest.TestCase):
    def test_both_roots_exist_for_every_language(self):
        segments = travel.load_path_segments()
        self.assertEqual(set(segments), {"travel", "travel_index"})
        repo = MAIN.parents[1]
        for key, by_language in segments.items():
            self.assertEqual(set(by_language), set(ORDER))
            for language, directory in by_language.items():
                with self.subTest(key=key, language=language):
                    self.assertTrue((repo / directory).is_dir(), f"{directory} is missing")

    def test_each_root_sits_under_its_own_language(self):
        for by_language in travel.load_path_segments().values():
            for language, directory in by_language.items():
                with self.subTest(language=language):
                    self.assertEqual(directory.parts[0], language)



class SparseLabelTests(unittest.TestCase):
    """An empty cell means the language has no wording of its own."""

    def test_a_sparse_label_is_absent_rather_than_empty(self):
        labels = travel.load_ui_labels()
        self.assertEqual(
            sorted(l for l in ORDER if "language_switcher" in labels[l]), ["hi", "ml", "pa"]
        )
        for language in ORDER:
            for key, value in labels[language].items():
                with self.subTest(language=language, key=key):
                    self.assertTrue(value)

    def test_the_country_page_keys_are_complete_in_every_language(self):
        labels = travel.load_ui_labels()
        required = {"credits", "footer", "hero_subtitle", "home", "photography",
                    "site_tagline", "travel"}
        for language in ORDER:
            with self.subTest(language=language):
                self.assertTrue(required <= set(labels[language]))

    def test_highlights_falls_back_to_english(self):
        labels = travel.load_ui_labels()
        self.assertEqual(labels["ml"]["highlights"], "പ്രധാനപ്പെട്ടവ")
        self.assertEqual(labels["fr"].get("highlights", "Highlights"), "Highlights")


class CityExonymTests(unittest.TestCase):
    """Any language may have an exonym; none of them needs its own table."""

    def test_french_exonyms_drive_the_french_filenames(self):
        self.assertEqual(travel.translated_city_name("Antwerp", "fr"), "Anvers")
        self.assertEqual(travel.translated_city_filename("Venice.html", "fr"), "Venise.html")

    def test_a_city_without_an_exonym_keeps_its_own_name(self):
        self.assertEqual(travel.translated_city_name("Lyon", "fr"), "Lyon")
        self.assertEqual(travel.translated_city_name("Berlin", "es"), "Berlin")

    def test_transliterating_languages_still_work(self):
        self.assertNotEqual(travel.translated_city_name("Vienna", "ml"), "Vienna")

    def test_no_language_has_a_table_of_its_own(self):
        translations = Path(travel.PLACE_NAMES_CSV).parent
        stray = [p.name for p in translations.glob("*.csv") if p.name.startswith(("french", "english"))]
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
