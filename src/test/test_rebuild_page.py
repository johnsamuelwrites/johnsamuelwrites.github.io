import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.rebuild_page import rebuild_html


class RebuildPageTests(unittest.TestCase):
    def test_rebuild_resolves_qids_and_preserves_svg_casing(self):
        html = """
        <html lang="zxx" data-abstract-page="local:Q1">
          <head><title>Q1</title></head>
          <body>
            <svg viewBox="0 0 10 10">
              <linearGradient id="g"><feGaussianBlur stdDeviation="2"/></linearGradient>
            </svg>
            <h1>Q1</h1>
            <p><span data-content="local:Q2">Q2</span> <a href="../Q3633.html">Q42761025</a></p>
          </body>
        </html>
        """
        labels = {
            "Q1": {"fr": "Titre"},
            "Q2": {"fr": "Par"},
        }

        rebuilt = rebuild_html(
            html,
            page_qid="Q1",
            language="fr",
            labels=labels,
            repo_root=Path("/repo"),
            abstract_path=Path("Q315/Q10.html"),
            target_path=Path("fr/page.html"),
            abstract_targets={Path("Q315/Q3633.html"): Path("fr/apropos.html")},
        )

        self.assertIn('viewBox="0 0 10 10"', rebuilt)
        self.assertIn("<linearGradient", rebuilt)
        self.assertIn("<feGaussianBlur", rebuilt)
        self.assertIn("<h1>Titre</h1>", rebuilt)
        self.assertIn("<span>Par</span>", rebuilt)
        self.assertIn(">John Samuel</a>", rebuilt)


if __name__ == "__main__":
    unittest.main()
