import json
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from links import BrokenLink, LinkChecker, LinkType, collect_html_files, write_json_report


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


if __name__ == "__main__":
    unittest.main()
