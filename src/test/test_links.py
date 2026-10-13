import json
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

import tempfile

from links import BrokenLink, LinkChecker, LinkType, collect_html_files, collect_links, write_json_report


class LinkCheckerTests(unittest.TestCase):
    def setUp(self):
        self.fixtures_root = Path(__file__).resolve().parent / "fixtures" / "links"

    def test_collect_html_files_respects_excluded_directories(self):
        root = self.fixtures_root / "collect"
        included = root / "page.html"

        html_files = collect_html_files(
            [str(root)], recursive=True, exclude_dirs=["skip-me"]
        )

        self.assertEqual(html_files, [str(included.resolve())])

    def test_internal_missing_link_is_reported(self):
        source = self.fixtures_root / "broken" / "index.html"

        checker = LinkChecker(
            check_external=False,
            check_internal=True,
            check_favicon=False,
            check_styles=False,
            check_scripts=False,
        )

        results = checker.check_files([str(source)])

        self.assertIn(str(source.resolve()), results)
        self.assertEqual(len(results[str(source.resolve())]), 1)
        broken_link = results[str(source.resolve())][0]
        self.assertIsInstance(broken_link, BrokenLink)
        self.assertEqual(broken_link.link_type, LinkType.INTERNAL)
        self.assertEqual(broken_link.error, "File not found")

    def test_json_report_contains_broken_link_details(self):
        source = self.fixtures_root / "broken" / "index.html"
        broken_link = BrokenLink(
            source_file=str(source.resolve()),
            url="missing.html",
            link_type=LinkType.INTERNAL,
            error="File not found",
        )
        report_path = self.fixtures_root / "broken-links-report.json"
        try:
            write_json_report(
                {str(source.resolve()): [broken_link]},
                report_path,
                fixed_favicon_files={str(source.resolve())},
            )
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_broken_links"], 1)
            self.assertEqual(
                payload["summary"]["fixed_favicon_files"],
                [str(source.resolve())],
            )
            self.assertEqual(
                payload["files"][str(source.resolve())][0]["error"],
                "File not found",
            )
        finally:
            if report_path.exists():
                report_path.unlink()


class LinkCollectorTests(unittest.TestCase):
    """The streaming collector must find the links a parsed tree would."""

    def test_anchors_links_and_scripts_are_collected_with_entities_decoded(self):
        page = collect_links(
            '<a href="a.html?x=1&amp;y=2">x</a><a name="top">no href</a>'
            '<link rel="icon stylesheet" href="s.css"/><script src="j.js"></script>'
            "<script>var a = '<a href=\"inline.html\">';</script>"
        )
        self.assertEqual(page.anchors, ["a.html?x=1&y=2"])
        self.assertEqual(page.links, [{"rel": "icon stylesheet", "href": "s.css"}])
        self.assertEqual(page.scripts, ["j.js"])


class TrackedFilesTests(unittest.TestCase):
    """CI checks links against git's file list: binary assets are not checked out."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name).resolve()
        self.page = root / "en" / "page.html"
        self.page.parent.mkdir()
        self.page.write_text(
            '<a href="../images/photo.png">p</a><a href="../images/gone.png">g</a>'
            '<a href="../images">d</a>',
            encoding="utf-8",
        )
        # The image is tracked but, as in CI's sparse checkout, not on disk.
        self.tracked = [self.page, root / "images" / "photo.png"]

    def tearDown(self):
        self.directory.cleanup()

    def errors(self, tracked):
        checker = LinkChecker(
            check_external=False, check_favicon=False, check_styles=False,
            check_scripts=False, tracked_files=tracked,
        )
        return {link.url: link.error for link in checker.check_files([str(self.page)]).get(str(self.page), [])}

    def test_a_tracked_file_that_is_not_checked_out_is_not_broken(self):
        errors = self.errors(self.tracked)
        self.assertNotIn("../images/photo.png", errors)
        self.assertEqual(errors["../images/gone.png"], "File not found")
        self.assertEqual(errors["../images"], "Path is not a file")

    def test_without_the_tracked_list_the_disk_decides(self):
        self.assertEqual(self.errors(None)["../images/photo.png"], "File not found")


if __name__ == "__main__":
    unittest.main()
