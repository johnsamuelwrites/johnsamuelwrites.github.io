import sys
import tempfile
import unittest
from pathlib import Path


MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from build_remaining_abstract_pages import rebase_missing_article_links


class RemainingAbstractLinkTests(unittest.TestCase):
    def test_rebases_source_links_but_retains_existing_q315_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "en/linguistics/index.html"
            article = root / "en/linguistics/human-languages.html"
            target = root / "Q315/Q7947/index.html"
            q315_home = root / "Q315/index.html"
            article.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            q315_home.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("", encoding="utf-8")
            article.write_text("", encoding="utf-8")
            q315_home.write_text("", encoding="utf-8")
            target.write_text(
                '<a href="human-languages.html">Article</a>'
                '<a href="../index.html">Q315 home</a>'
                '<a href="https://example.com/">External</a>',
                encoding="utf-8",
            )

            changed = rebase_missing_article_links(source, target)

            self.assertEqual(changed, 1)
            result = target.read_text(encoding="utf-8")
            self.assertIn(
                'href="../../en/linguistics/human-languages.html"', result
            )
            self.assertIn('href="../index.html"', result)
            self.assertIn('href="https://example.com/"', result)


if __name__ == "__main__":
    unittest.main()
