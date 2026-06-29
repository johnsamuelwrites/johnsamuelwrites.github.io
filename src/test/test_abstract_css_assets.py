import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.css_assets import (
    CSSAssetError,
    check_group,
    load_groups,
    migrate_group,
    stylesheet_href,
)


class AbstractCSSAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manifest = self.root / "css-assets.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "version": 1,
                    "groups": [
                        {
                            "id": "Q1",
                            "asset": "Q315/assets/css/pages/Q1.css",
                            "pages": [
                                "Q315/Q1.html",
                                "en/topic/page.html",
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        for page in ("Q315/Q1.html", "en/topic/page.html"):
            path = self.root / page
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "<html>\n  <head>\n"
                "    <style>\n      body { color: navy; }\n    </style>\n"
                "  </head>\n</html>\n",
                encoding="utf-8",
            )
        self.group = load_groups(self.manifest)[0]

    def tearDown(self):
        self.temporary.cleanup()

    def test_relative_href_is_computed_for_each_page(self):
        self.assertEqual(
            stylesheet_href(self.group.pages[0], self.group.asset),
            "assets/css/pages/Q1.css",
        )
        self.assertEqual(
            stylesheet_href(self.group.pages[1], self.group.asset),
            "../../Q315/assets/css/pages/Q1.css",
        )

    def test_migration_extracts_css_and_rewrites_all_pages(self):
        changed = migrate_group(self.group, self.root)

        self.assertEqual(changed, 3)
        asset = self.root / self.group.asset
        self.assertEqual(asset.read_text(encoding="utf-8"), "body { color: navy; }\n")
        for relative_page in self.group.pages:
            html = (self.root / relative_page).read_text(encoding="utf-8")
            self.assertNotIn("<style>", html)
            self.assertIn('data-q315-css="Q1"', html)
        self.assertEqual(check_group(self.group, self.root), [])

    def test_migration_is_idempotent(self):
        migrate_group(self.group, self.root)
        self.assertEqual(migrate_group(self.group, self.root), 0)

    def test_migration_repairs_an_existing_relative_link(self):
        migrate_group(self.group, self.root)
        page = self.root / self.group.pages[0]
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                'href="assets/css/pages/Q1.css"',
                'href="../../wrong/Q1.css"',
            ),
            encoding="utf-8",
        )

        self.assertEqual(migrate_group(self.group, self.root), 1)
        self.assertEqual(check_group(self.group, self.root), [])

    def test_migration_refuses_different_css(self):
        second = self.root / self.group.pages[1]
        second.write_text(
            second.read_text(encoding="utf-8").replace("navy", "maroon"),
            encoding="utf-8",
        )

        with self.assertRaises(CSSAssetError):
            migrate_group(self.group, self.root)

        self.assertFalse((self.root / self.group.asset).exists())
        self.assertIn(
            "<style>",
            (self.root / self.group.pages[0]).read_text(encoding="utf-8"),
        )

    def test_authoritative_page_css_replaces_translated_drift(self):
        group = type(self.group)(
            identifier=self.group.identifier,
            asset=self.group.asset,
            pages=self.group.pages,
            authoritative_page=self.group.pages[0],
        )
        translated = self.root / group.pages[1]
        translated.write_text(
            translated.read_text(encoding="utf-8").replace("navy", "maroon"),
            encoding="utf-8",
        )

        migrate_group(group, self.root)

        self.assertEqual(
            (self.root / group.asset).read_text(encoding="utf-8"),
            "body { color: navy; }\n",
        )
        self.assertNotIn(
            "<style>", translated.read_text(encoding="utf-8")
        )


class CollectionDiscoveryTests(unittest.TestCase):
    def test_collection_discovers_abstract_page_and_language_alternates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            abstract = root / "Q315/Q9"
            abstract.mkdir(parents=True)
            pages = {
                "en": root / "en/topic.html",
                "fr": root / "fr/sujet.html",
            }
            for page in pages.values():
                page.parent.mkdir(parents=True)
                page.write_text("<html></html>", encoding="utf-8")
            (abstract / "index.html").write_text(
                '<link rel="alternate" hreflang="en" '
                'href="../../en/topic.html">\n'
                '<link rel="alternate" hreflang="fr" '
                'href="../../fr/sujet.html">\n'
                "<style>body { color: navy; }</style>",
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "groups": [],
                        "collections": [
                            {
                                "id": "test",
                                "abstract_root": "Q315/Q9",
                                "asset_directory": "Q315/assets/css/pages",
                                "index_asset": "Q315/assets/css/collections/Q9.css",
                                "languages": ["en", "fr"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            groups = load_groups(manifest, root)

            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].identifier, "Q9")
            self.assertEqual(
                groups[0].asset, Path("Q315/assets/css/collections/Q9.css")
            )
            self.assertEqual(
                groups[0].pages,
                (
                    Path("Q315/Q9/index.html"),
                    Path("en/topic.html"),
                    Path("fr/sujet.html"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
