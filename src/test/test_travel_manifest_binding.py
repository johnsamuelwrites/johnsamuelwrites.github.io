import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.bind_travel_manifest import bind_page


class TravelManifestBindingTests(unittest.TestCase):
    def test_binding_targets_the_requested_occurrence_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<span property="name">Q315</span>\n'
                '<span property="name">Research</span>\n'
                '<span property="name">Writings</span>\n',
                encoding="utf-8",
            )

            relative, output, errors = bind_page(
                root,
                "Q1",
                Path("page.html"),
                {("span", "", "", 2): "Q4050"},
            )

            self.assertEqual(relative, Path("page.html"))
            self.assertEqual(errors, [])
            self.assertIn('<span property="name">Q315</span>', output)
            self.assertIn('<span property="name">Research</span>', output)
            self.assertIn(
                '<span property="name" data-content="local:Q4050">Q4050</span>',
                output,
            )

    def test_binding_repairs_owned_misplaced_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<span property="name" data-content="local:Q4050">Q315</span>\n'
                '<span property="name">Research</span>\n'
                '<span property="name">Writings</span>\n',
                encoding="utf-8",
            )

            _, output, errors = bind_page(
                root,
                "Q1",
                Path("page.html"),
                {("span", "", "", 2): "Q4050"},
            )

            self.assertEqual(errors, [])
            self.assertIn('<span property="name">Q315</span>', output)
            self.assertIn(
                '<span property="name" data-content="local:Q4050">Q4050</span>',
                output,
            )

    def test_binding_replaces_nested_readable_fallback_with_qid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<p class="footer-credits">© 2025 <strong>Q42761025</strong> '
                "• Travel & Photography Explorer</p>",
                encoding="utf-8",
            )

            _, output, errors = bind_page(
                root,
                "Q1",
                Path("page.html"),
                {("p", "footer-credits", "", 0): "Q4051"},
            )

            self.assertEqual(errors, [])
            self.assertEqual(
                output,
                '<p class="footer-credits" data-content="local:Q4051">Q4051</p>',
            )

    def test_parent_binding_wins_over_nested_child_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<p>Some <a href="./index.html">nested text</a> here.</p>',
                encoding="utf-8",
            )

            _, output, errors = bind_page(
                root,
                "Q1",
                Path("page.html"),
                {
                    ("p", "", "", 0): "Q4013",
                    ("a", "", "", 0): "Q4012",
                },
            )

            self.assertEqual(errors, [])
            self.assertEqual(output, '<p data-content="local:Q4013">Q4013</p>')


if __name__ == "__main__":
    unittest.main()
