import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from config import ALLOWED_UNREFERENCED_HTML_FILES, EXCLUDED_DIRECTORIES
from html_generator import HTMLTranslator
from manifest import BuildManifest, fingerprint_paths
from metadata import update_metadata_content
from paths import REPO_ROOT, repo_url_for, search_index_path, to_repo_relative
from site_text import strip_author_from_title
from translate_manager import HTMLTranslationExtractor


class StaticSiteToolTests(unittest.TestCase):
    def test_strip_author_from_title_handles_known_suffixes(self):
        self.assertEqual(
            strip_author_from_title("Example Article: John Samuel"),
            "Example Article",
        )

    def test_repo_url_for_normalizes_relative_paths(self):
        self.assertEqual(repo_url_for("en/blog/example.html"), "en/blog/example.html")

    def test_to_repo_relative_preserves_repo_relative_path(self):
        absolute = (REPO_ROOT / "en" / "blog" / "example.html").resolve()
        self.assertEqual(
            to_repo_relative(absolute),
            Path("en") / "blog" / "example.html",
        )

    def test_search_index_path_uses_language_root(self):
        self.assertEqual(search_index_path("en"), REPO_ROOT / "en" / "search-index.json")

    def test_default_site_check_exclusions_skip_tooling_and_known_entrypoints(self):
        self.assertIn("src", EXCLUDED_DIRECTORIES)
        self.assertIn("ui", EXCLUDED_DIRECTORIES)
        self.assertIn("404.html", ALLOWED_UNREFERENCED_HTML_FILES)
        self.assertIn("license.html", ALLOWED_UNREFERENCED_HTML_FILES)

    def test_update_metadata_content_inserts_jsonld(self):
        existing_repo_file = REPO_ROOT / "index.html"
        updated = update_metadata_content(
            "<html><head><title>Example: John Samuel</title></head><body></body></html>",
            str(existing_repo_file),
        )

        self.assertIn("application/ld+json", updated)
        self.assertIn('"headline": "Example"', updated)

    def test_translation_rules_are_shared(self):
        self.assertEqual(HTMLTranslator.SKIP_TAGS, HTMLTranslationExtractor.SKIP_TAGS)
        self.assertEqual(
            HTMLTranslator.TRANSLATABLE_ATTRS,
            HTMLTranslationExtractor.TRANSLATABLE_ATTRS,
        )

    def test_manifest_update_marks_existing_outputs_current(self):
        manifest_path = REPO_ROOT / "analysis" / "test-build-manifest.json"
        source = REPO_ROOT / "src" / "main" / "README.md"
        output = REPO_ROOT / "README.md"
        manifest = BuildManifest(manifest_path=manifest_path)

        with mock.patch.object(BuildManifest, "_save", autospec=True, return_value=None):
            manifest.update("unit-test", [source], [output], extra="v1")

        self.assertTrue(manifest.is_current("unit-test", [source], [output], extra="v1"))
        self.assertFalse(manifest.is_current("unit-test", [source], [output], extra="v2"))

    def test_fingerprint_changes_when_sources_change(self):
        source_a = REPO_ROOT / "src" / "main" / "README.md"
        source_b = REPO_ROOT / "src" / "main" / "main.py"
        self.assertNotEqual(
            fingerprint_paths([source_a]),
            fingerprint_paths([source_b]),
        )


if __name__ == "__main__":
    unittest.main()
