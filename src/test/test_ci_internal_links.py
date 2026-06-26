import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from ci_internal_links import (
    FULL_SCAN_IGNORED_DIRS,
    is_ignored_html_file,
    resolve_all_html_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def chdir(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class FullSiteScanTests(unittest.TestCase):
    def test_full_scan_excludes_source_tree(self):
        """The full-site scan must skip src/ so test fixtures are not flagged."""
        self.assertIn("src", FULL_SCAN_IGNORED_DIRS)

    def test_is_ignored_respects_custom_dirs(self):
        path = Path("es/templates/page.html")
        self.assertTrue(is_ignored_html_file(path))
        self.assertFalse(is_ignored_html_file(Path("es/viajes/index.html")))

    def test_resolve_all_html_files_collects_site_and_omits_fixtures(self):
        with chdir(REPO_ROOT):
            files = resolve_all_html_files()

        self.assertTrue(files, "expected the repository to contain HTML files")
        # The intentionally broken fixture under src/ must never be returned.
        self.assertFalse(
            any(f"{os.sep}src{os.sep}" in path for path in files),
            "full-site scan should exclude the src/ tree",
        )
        # A representative real page should be present.
        index = (REPO_ROOT / "en" / "index.html").resolve()
        if index.exists():
            self.assertIn(str(index), files)


if __name__ == "__main__":
    unittest.main()
