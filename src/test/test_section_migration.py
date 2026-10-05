import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract import section_migration as sm
from languages import ORDER


def page(key, parent, paths, item="", abstract_path=""):
    return sm.Page(
        key=key, section="s", parent=parent, item=item, abstract_path=abstract_path,
        title_item="", name_slot="", labels=("L", "L"),
        paths={language: paths.get(language, f"{language}/x/{key}.html") for language in ORDER},
    )


def body(markup):
    return f"<html><head></head><body>{markup}</body></html>"


def prepared(markup):
    source = sm.prepare_english(body(markup))
    return source[source.index("<body>") + len("<body>"):source.index("</body>")]


class RoutesTests(unittest.TestCase):
    def test_route_and_segment_come_from_the_path(self):
        p = page("egg", "nature", {"hi": "hi/अनुसंधान/3डी/प्रकृति/अंडा.html", "en": "en/research/3d/index.html"})
        self.assertEqual(p.route("hi"), "अनुसंधान/3डी/प्रकृति/अंडा.html")
        self.assertEqual(p.segment("hi"), "अंडा")
        self.assertEqual(p.segment("en"), "3d")

    def test_default_abstract_path_nests_by_ancestor_items(self):
        pages = {
            "root": page("root", "Q3636", {}, item="Q1"),
            "hub": page("hub", "root", {}, item="Q2"),
            "leaf": page("leaf", "hub", {}, item="Q3"),
        }
        self.assertEqual(sm.default_abstract_path(pages, pages["root"]), "Q315/Q3636/Q1/index.html")
        self.assertEqual(sm.default_abstract_path(pages, pages["hub"]), "Q315/Q3636/Q1/Q2.html")
        self.assertEqual(sm.default_abstract_path(pages, pages["leaf"]), "Q315/Q3636/Q1/Q2/Q3.html")

    def test_route_corrections_rewrite_only_differing_statements(self):
        p = page("egg", "nature", {"ml": "ml/ഗവേഷണം/3ഡി/മുട്ട.html"})
        claim = lambda prop, language, text: {
            "id": f"Q3${prop}{language}",
            "mainsnak": {"property": prop, "datavalue": {"value": {"language": language, "text": text}}},
        }
        entity = {"claims": {
            "P38": [claim("P38", "ml", "മുട്ട")],
            "P39": [claim("P39", "ml", "ഗവേഷണം/3d/മുട്ട.html")],
        }}
        changed = sm.route_corrections(entity, p)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["id"], "Q3$P39ml")
        self.assertEqual(changed[0]["mainsnak"]["datavalue"]["value"]["text"], "ഗവേഷണം/3ഡി/മുട്ട.html")


class InlineMarkupTests(unittest.TestCase):
    def test_label_and_description_become_two_spans(self):
        self.assertEqual(
            prepared("<li><strong>Efficiency:</strong> Faster work</li>"),
            "<li><strong><span>Efficiency:</span></strong> <span>Faster work</span></li>",
        )

    def test_book_title_keeps_the_following_punctuation(self):
        self.assertEqual(
            prepared("<li><b>Color</b>, Betty Edwards</li>"),
            "<li><b><span>Color</span></b><span>, Betty Edwards</span></li>",
        )

    def test_leading_link_keeps_the_link_and_wraps_its_text(self):
        self.assertEqual(
            prepared('<li><a href="x">Blender</a> — the tool</li>'),
            '<li><a href="x">Blender</a> <span>— the tool</span></li>',
        )

    def test_keys_split_into_label_key_and_phrase(self):
        self.assertEqual(
            prepared('<li>Alternative: <span class="kbd">Alt</span> emulates</li>'),
            '<li><span>Alternative:</span> <span class="kbd">Alt</span> <span>emulates</span></li>',
        )

    def test_emphasis_inside_a_sentence_is_unwrapped(self):
        self.assertEqual(
            prepared("<p>Dedicated to my <strong>teachers</strong> who taught.</p>"),
            "<p>Dedicated to my teachers who taught.</p>",
        )

    def test_hero_prose_is_wrapped_in_a_paragraph(self):
        self.assertIn('<div class="hero-description">\n    <p>Some prose.</p>', prepared(
            '<div class="hero-description">Some\n prose.</div>'
        ))

    def test_label_before_a_nested_list_becomes_a_span(self):
        self.assertIn("<strong><span>Save</span></strong>", prepared("<li><strong>Save</strong><ul><li>x</li></ul></li>"))


class CompositionTests(unittest.TestCase):
    def test_links_fill_the_paragraph_placeholders_in_order(self):
        rows = [
            {"slot": "p|||0", "kind": "sentence", "ordinal": "1", "qid": "", **{l: "" for l in ORDER}},
            {"slot": "a|||0", "kind": "content", "ordinal": "", "qid": "", **{l: "" for l in ORDER}},
        ]
        source = '<p>See <a href="d.html">Drawing</a> then.</p>'
        targets = {("p", "", "", 0): "Voir le projet () puis.", ("a", "", "", 0): "Dessin"}
        result = sm.with_paragraph_anchors(source, rows, targets, "fr/x.html")
        self.assertEqual(result, '<p>Voir le projet (<a href="d.html">Dessin</a>) puis.</p>')

    def test_placeholder_count_must_match_the_links(self):
        rows = [{"slot": "p|||0", "kind": "sentence", "ordinal": "1", "qid": "", **{l: "" for l in ORDER}}]
        with self.assertRaises(ValueError):
            sm.with_paragraph_anchors('<p>A <a href="d">x</a></p>', rows, {("p", "", "", 0): "no link"}, "x")

    def test_created_qids_pair_batch_markers_with_the_log(self):
        with tempfile.TemporaryDirectory() as directory:
            batch, log = Path(directory, "b"), Path(directory, "l")
            batch.write_text("# token M1\nCREATE\n\n# token M2\nCREATE\n", encoding="utf-8")
            log.write_text("Validated 2\nWrote Q10\nWrote Q11\nCompleted\n", encoding="utf-8")
            self.assertEqual(sm.created_qids(batch, log, "token"), [("M1", "Q10"), ("M2", "Q11")])
            log.write_text("Wrote Q10\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                sm.created_qids(batch, log, "token")


if __name__ == "__main__":
    unittest.main()
