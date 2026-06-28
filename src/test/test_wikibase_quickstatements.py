import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from wikibase_quickstatements import (
    LANGUAGE_ITEMS,
    FormInference,
    Page,
    blocking_warnings,
    git_creation_dates,
    infer_form,
    normalize_url,
    read_existing_urls,
    render_page,
)


FORM_TYPES = {
    "photography page": "Q1044",
    "blog post": "Q1047",
    "course page": "Q1043",
    "slideshow": "Q1033",
    "course assignment": "Q1035",
    "course reference": "Q1042",
    "course examination": "Q1046",
    "course introduction": "Q1045",
}


class WikibaseQuickStatementsTests(unittest.TestCase):
    def test_normalize_url_encodes_spaces_and_unicode(self):
        self.assertEqual(
            normalize_url("https://johnsamuel.info/pa/a b/ਪੰਨਾ.html"),
            "https://johnsamuel.info/pa/a%20b/%E0%A8%AA%E0%A9%B0%E0%A8%A8%E0%A8%BE.html",
        )

    def test_existing_url_reader_requires_and_normalizes_url(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "query.csv"
            with path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=["item", "title", "url"])
                writer.writeheader()
                writer.writerow(
                    {
                        "item": "Q1",
                        "title": "Example",
                        "url": "https://johnsamuel.info/en/a page.html",
                    }
                )
            self.assertIn(
                "https://johnsamuel.info/en/a%20page.html",
                read_existing_urls(path),
            )

    def test_form_inference_uses_ordered_course_rules(self):
        cases = {
            "en/teaching/courses/2023/DS4C/introduction.html": "course introduction",
            "en/teaching/courses/2023/DS4C/class4.html": "slideshow",
            "en/teaching/courses/2019/DataMining/references.html": "course reference",
            "fr/enseignement/cours/2025/C/tp2.html": "course assignment",
            "en/teaching/courses/2017/DataMining/questions1.html": "course examination",
            "en/teaching/courses/2023/DataScience/index.html": "course page",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(infer_form(path, FORM_TYPES).label, expected)

    def test_multilingual_travel_is_photography(self):
        for path in (
            "en/travel/bridges.html",
            "fr/voyages/ponts.html",
            "it/viaggi/ponti.html",
            "ml/യാത്രകൾ/പാലങ്ങൾ.html",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    infer_form(path, FORM_TYPES).label, "photography page"
                )

    def test_photography_slides_and_transcripts_are_classified(self):
        self.assertEqual(
            infer_form("en/photography/cities/France/Lyon.html", FORM_TYPES).label,
            "photography page",
        )
        self.assertEqual(
            infer_form("en/slides/2025/Event/slides.html", FORM_TYPES).label,
            "slideshow",
        )
        self.assertEqual(
            infer_form(
                "en/slides/2021/Event/transcript-Event.html", FORM_TYPES
            ).label,
            "transcript",
        )

    @mock.patch("wikibase_quickstatements.subprocess.run")
    def test_git_creation_dates_uses_earliest_commit_only(self, run):
        run.return_value.stdout = (
            "--200\n"
            "en/example.html\n"
            "--100\n"
            "en/example.html\n"
            "--150\n"
            "en/other.html\n"
        )
        self.assertEqual(
            git_creation_dates(Path("/repo")),
            {"en/example.html": 100, "en/other.html": 150},
        )
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["git", "-C", "/repo"])
        self.assertIn("core.quotepath=false", command)
        self.assertIn("log", command)

    def test_supplied_spanish_language_item_is_rendered(self):
        page = Page(
            path=Path("es/viajes/puentes.html"),
            language="es",
            title="Puentes",
            url="https://johnsamuel.info/es/viajes/puentes.html",
            created=0,
            form=FormInference("Q1044", "photography page", "travel directory"),
        )
        self.assertEqual(blocking_warnings(page), [])
        rendered = render_page(page)
        self.assertIn('LAST|Les|"Puentes"', rendered)
        self.assertIn("LAST|P17|Q1765", rendered)

    def test_render_page_uses_git_timestamp_value_and_escapes_title(self):
        page = Page(
            path=Path("en/blog/example.html"),
            language="en",
            title='A "quoted" title',
            url="https://johnsamuel.info/en/blog/example.html",
            created=0,
            form=FormInference("Q1047", "blog post", "blog path"),
        )
        rendered = render_page(page)
        self.assertIn('LAST|Len|"A \\"quoted\\" title"', rendered)
        self.assertIn(f"LAST|P17|{LANGUAGE_ITEMS['en']}", rendered)
        self.assertIn("LAST|P10|+1970-01-01T00:00:00Z/11", rendered)
        self.assertIn("LAST|P29|Q1047", rendered)


if __name__ == "__main__":
    unittest.main()
