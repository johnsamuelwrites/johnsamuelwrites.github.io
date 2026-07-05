import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.discover_content_migration import abstract_sources, discover


def page(alternates, *, abstract="", generated=False):
    attributes = (
        f' data-abstract-page="local:{abstract}" data-abstract-version="1"'
        if abstract
        else ""
    )
    generator = (
        '<meta name="generator" content="Q315 renderer">' if generated else ""
    )
    links = "".join(
        f'<link rel="alternate" hreflang="{language}" href="{href}">'
        for language, href in alternates.items()
    )
    return f"<html{attributes}><head>{generator}{links}</head></html>"


class ContentMigrationDiscoveryTests(unittest.TestCase):
    def test_legacy_pages_are_temporary_sources_for_an_existing_abstract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("en/topic.html", "fr/sujet.html", "Q315/Q10.html"):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / "en/topic.html").write_text(
                page({}),
                encoding="utf-8",
            )
            (root / "fr/sujet.html").write_text(
                page({}),
                encoding="utf-8",
            )
            (root / "Q315/Q10.html").write_text(
                page(
                    {"en": "../en/topic.html", "fr": "../fr/sujet.html"},
                    abstract="Q10",
                ),
                encoding="utf-8",
            )

            rows = discover(root)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["page_qid"], "Q10")
            self.assertEqual(rows[0]["migration_state"], "abstract-authored")
            self.assertEqual(rows[0]["render_ownership"], "legacy")
            self.assertEqual(rows[0]["en_source"], "en/topic.html")
            self.assertEqual(rows[0]["target_fr"], "fr/sujet.html")

    def test_blog_index_is_excluded_from_abstract_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "en/blog.html", "fr/blog.html",
                "en/topic.html", "fr/sujet.html",
                "Q315/Q3634.html", "Q315/Q10.html",
            ):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text(page({}), encoding="utf-8")
            # Blog index abstract page: its English target is a blog.py output.
            (root / "Q315/Q3634.html").write_text(
                page(
                    {"en": "../en/blog.html", "fr": "../fr/blog.html"},
                    abstract="Q3634",
                ),
                encoding="utf-8",
            )
            (root / "Q315/Q10.html").write_text(
                page(
                    {"en": "../en/topic.html", "fr": "../fr/sujet.html"},
                    abstract="Q10",
                ),
                encoding="utf-8",
            )

            qids = {qid for qid, _ in abstract_sources(root)}

            self.assertIn("Q10", qids)
            self.assertNotIn("Q3634", qids)

    def test_generated_pages_are_targets_and_never_migration_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("en/topic.html", "fr/sujet.html", "Q315/Q10.html"):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
            alternates_en = {"en": "topic.html", "fr": "../fr/sujet.html"}
            alternates_fr = {"en": "../en/topic.html", "fr": "sujet.html"}
            (root / "en/topic.html").write_text(
                page(alternates_en, generated=True), encoding="utf-8"
            )
            (root / "fr/sujet.html").write_text(
                page(alternates_fr, generated=True), encoding="utf-8"
            )
            (root / "Q315/Q10.html").write_text(
                page(
                    {"en": "../en/topic.html", "fr": "../fr/sujet.html"},
                    abstract="Q10",
                ),
                encoding="utf-8",
            )

            row = discover(root)[0]

            self.assertEqual(row["migration_state"], "generated-owner")
            self.assertEqual(row["render_ownership"], "abstract")
            self.assertEqual(row["en_source"], "")
            self.assertEqual(row["fr_source"], "")
            self.assertEqual(row["target_en"], "en/topic.html")


if __name__ == "__main__":
    unittest.main()
