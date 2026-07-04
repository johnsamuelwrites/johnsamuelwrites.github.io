import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.bind_abstract_page_qids import (
    apply,
    collect,
    page_qid_from_path,
    stamp_html,
)


class PageQidFromPathTests(unittest.TestCase):
    def test_identity_is_taken_from_the_path(self):
        root = Path("/repo")
        cases = {
            "Q315/index.html": "Q315",
            "Q315/Q3062/index.html": "Q3062",
            "Q315/Q3062/Q3027.html": "Q3027",
            "Q315/Q3062/Q3025/Q3067/Q3090.html": "Q3090",
        }
        for relative, expected in cases.items():
            self.assertEqual(
                page_qid_from_path(root, root / relative), expected, relative
            )

    def test_a_path_without_an_encoded_qid_yields_none(self):
        root = Path("/repo")
        self.assertIsNone(page_qid_from_path(root, root / "Q315/about/team.html"))


class StampTests(unittest.TestCase):
    def test_declaration_is_injected_and_lang_preserved(self):
        stamped = stamp_html('<!DOCTYPE html>\n<html lang="zxx">\n', "Q3027")
        self.assertIn('lang="zxx"', stamped)
        self.assertIn('data-abstract-page="local:Q3027"', stamped)
        self.assertIn('data-abstract-version="1"', stamped)


class ApplyTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, html: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def test_check_reports_without_writing_then_apply_stamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "Q315/Q3062/Q3027.html", '<html lang="zxx"></html>')
            self._write(
                root,
                "Q315/Q3062/index.html",
                '<html lang="zxx" data-abstract-page="local:Q3062"'
                ' data-abstract-version="1"></html>',
            )

            pending, errors = apply(root, check=True)
            self.assertEqual(errors, [])
            self.assertEqual(pending, 1)
            self.assertNotIn(
                "data-abstract-page",
                (root / "Q315/Q3062/Q3027.html").read_text(encoding="utf-8"),
            )

            pending, errors = apply(root, check=False)
            self.assertEqual(pending, 1)
            self.assertIn(
                'data-abstract-page="local:Q3027"',
                (root / "Q315/Q3062/Q3027.html").read_text(encoding="utf-8"),
            )
            # Rerunning is a no-op: the declaration is already present.
            pending, errors = apply(root, check=False)
            self.assertEqual(pending, 0)

    def test_a_conflicting_declaration_is_reported_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root,
                "Q315/Q3062/Q3027.html",
                '<html lang="zxx" data-abstract-page="local:Q9999"'
                ' data-abstract-version="1"></html>',
            )
            _, errors = collect(root)
            self.assertTrue(any("Q9999" in error and "Q3027" in error for error in errors))

    def test_colliding_page_qids_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, "Q315/Q3062/index.html", '<html lang="zxx"></html>')
            self._write(root, "Q315/Q3062.html", '<html lang="zxx"></html>')
            _, errors = collect(root)
            self.assertTrue(any("collides" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
