import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.repair_structure import Tree, apply_insertions, plan_page

CARD = (
    '<a class="gallery-card"><div class="card-content">'
    '<h3 class="card-title">{title}</h3>{desc}</div></a>'
)


def grid(cards):
    return '<div class="grid">' + "".join(cards) + "</div>"


def template():
    return grid([
        CARD.format(title="A", desc='<p class="card-description" data-content="local:Q1">Q1</p>'),
        CARD.format(title="B", desc='<p class="card-description" data-content="local:Q2">Q2</p>'),
    ])


LABELS = {
    "Q1": {"identifier": "Q1", "itemtype": "Q3185", "en": "One", "ml": "ml-one"},
    "Q2": {"identifier": "Q2", "itemtype": "Q3185", "en": "Two", "ml": "ml-two"},
}


class RepairStructureTests(unittest.TestCase):
    def test_inserts_missing_child_positionally(self):
        page_html = grid([
            CARD.format(title="അ", desc=""),
            CARD.format(title="ബ", desc=""),
        ])
        insertions, skipped = plan_page(Tree(template()), Tree(page_html), LABELS, "ml")

        self.assertEqual(skipped, [])
        self.assertEqual(len(insertions), 2)
        result = apply_insertions(page_html, insertions)
        self.assertIn('<p class="card-description">ml-one</p>', result)
        self.assertIn('<p class="card-description">ml-two</p>', result)
        # inserted right after the corresponding card-title, before </div>
        self.assertLess(result.index("ml-one"), result.index("ബ"))

    def test_no_insertion_when_child_present(self):
        page_html = grid([
            CARD.format(title="A", desc='<p class="card-description">already</p>'),
            CARD.format(title="B", desc='<p class="card-description">present</p>'),
        ])
        insertions, _ = plan_page(Tree(template()), Tree(page_html), LABELS, "ml")

        self.assertEqual(insertions, [])

    def test_container_count_mismatch_is_skipped_not_inserted(self):
        # Page has only one card where the template has two: unsafe to map.
        page_html = grid([CARD.format(title="അ", desc="")])
        insertions, skipped = plan_page(Tree(template()), Tree(page_html), LABELS, "ml")

        self.assertEqual(insertions, [])
        self.assertTrue(skipped)
        self.assertIn("card-description", skipped[0])

    def test_missing_label_value_is_not_inserted(self):
        page_html = grid([
            CARD.format(title="A", desc=""),
            CARD.format(title="B", desc=""),
        ])
        labels = {**LABELS, "Q2": {"identifier": "Q2", "itemtype": "Q3185", "en": "Two"}}
        insertions, _ = plan_page(Tree(template()), Tree(page_html), labels, "ml")

        # Q1 has an ml label, Q2 does not -> only one insertion.
        self.assertEqual(len(insertions), 1)

    def test_composed_result_types_are_ignored(self):
        tmpl = grid([
            '<a class="gallery-card"><div class="card-content">'
            '<h3 class="card-title">A</h3>'
            '<p class="card-description" data-content="local:Q9">Q9</p></div></a>'
        ])
        page_html = grid([
            '<a class="gallery-card"><div class="card-content">'
            '<h3 class="card-title">A</h3></div></a>'
        ])
        labels = {"Q9": {"identifier": "Q9", "itemtype": "Q3835", "en": "x", "ml": "y"}}
        insertions, _ = plan_page(Tree(tmpl), Tree(page_html), labels, "ml")

        self.assertEqual(insertions, [])


if __name__ == "__main__":
    unittest.main()
