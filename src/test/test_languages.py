#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import re
import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

import languages
from config import SUPPORTED_LANGUAGES
from translation_config import DEFAULT_TARGET_LANGS, SOURCE_LANG


class RegistryTests(unittest.TestCase):
    def test_every_language_is_complete(self):
        for language in languages.LANGUAGES:
            with self.subTest(code=language.code):
                self.assertTrue(re.fullmatch(r"[a-z]{2}", language.code))
                self.assertTrue(language.english_name)
                self.assertTrue(language.endonym)

    def test_codes_are_unique(self):
        self.assertEqual(len(languages.ORDER), len(set(languages.ORDER)))

    def test_english_comes_first_and_is_the_source(self):
        self.assertEqual(languages.ORDER[0], languages.SOURCE)
        self.assertNotIn(languages.SOURCE, languages.TARGETS)
        self.assertEqual(len(languages.TARGETS), len(languages.ORDER) - 1)

    def test_a_published_directory_exists_for_every_language(self):
        repo = MAIN.parents[1]
        for code in languages.ORDER:
            with self.subTest(code=code):
                self.assertTrue((repo / code).is_dir(), f"{code}/ is missing")

    def test_no_undeclared_language_directory(self):
        """A language directory with no registry entry would never be generated."""
        repo = MAIN.parents[1]
        # Two-letter directories that are not language roots.
        NOT_LANGUAGES = {"ui"}
        looks_like_language = {
            path.name
            for path in repo.iterdir()
            if path.is_dir() and re.fullmatch(r"[a-z]{2}", path.name)
        } - NOT_LANGUAGES
        self.assertEqual(looks_like_language - set(languages.ORDER), set())

    def test_is_supported(self):
        self.assertTrue(languages.is_supported("ml"))
        self.assertFalse(languages.is_supported("de"))


class SingleSourceTests(unittest.TestCase):
    """Every consumer must agree with the registry, not keep its own copy."""

    def test_config_derives_from_the_registry(self):
        self.assertEqual(list(SUPPORTED_LANGUAGES), list(languages.ORDER))
        self.assertEqual(SUPPORTED_LANGUAGES, languages.ENGLISH_NAMES)

    def test_translation_targets_derive_from_the_registry(self):
        self.assertEqual(SOURCE_LANG, languages.SOURCE)
        self.assertEqual(DEFAULT_TARGET_LANGS, list(languages.TARGETS))

    def test_german_and_dutch_are_no_longer_translation_targets(self):
        # They were listed as defaults but the site has never published them.
        self.assertNotIn("de", DEFAULT_TARGET_LANGS)
        self.assertNotIn("nl", DEFAULT_TARGET_LANGS)

    def test_no_module_redeclares_the_language_set(self):
        pattern = re.compile(r'"en",\s*"fr",\s*"ml",\s*"pa",\s*"hi"')
        offenders = [
            path.relative_to(MAIN).as_posix()
            for path in MAIN.rglob("*.py")
            if path.name != "languages.py" and pattern.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
