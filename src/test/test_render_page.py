import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.render_page import (
    SlotRewriter,
    inject_generator_meta,
    template_bindings,
)


def rewrite(source, targets):
    rewriter = SlotRewriter(source, targets)
    return rewriter.rewrite(), rewriter


class SlotRewriterTests(unittest.TestCase):
    def test_rewrites_bound_slot_and_leaves_siblings(self):
        source = '<p class="a">Bonjour</p><p class="a">World</p>'
        result, rw = rewrite(source, {("p", "a", "", 0): "Salut"})

        self.assertEqual(result, '<p class="a">Salut</p><p class="a">World</p>')
        self.assertEqual(rw.rewritten, {("p", "a", "", 0)})
        self.assertEqual(rw.applied, {("p", "a", "", 0)})

    def test_matching_text_is_not_rewritten(self):
        source = '<p class="a">World</p>'
        result, rw = rewrite(source, {("p", "a", "", 0): "World"})

        self.assertEqual(result, source)
        self.assertEqual(rw.rewritten, set())
        self.assertEqual(rw.applied, {("p", "a", "", 0)})

    def test_whitespace_and_entities_normalized_before_comparison(self):
        source = '<span class="s">R&amp;D\n  team</span>'
        # Decoded, collapsed text already equals the label, so nothing changes.
        result, rw = rewrite(source, {("span", "s", "", 0): "R&D team"})

        self.assertEqual(result, source)
        self.assertEqual(rw.rewritten, set())

    def test_replacement_text_is_escaped(self):
        source = '<span class="s">old</span>'
        result, _ = rewrite(source, {("span", "s", "", 0): "A & B <x>"})

        self.assertEqual(result, '<span class="s">A &amp; B &lt;x&gt;</span>')

    def test_element_with_child_is_left_structural(self):
        source = '<p class="a">text <b>x</b></p>'
        result, rw = rewrite(source, {("p", "a", "", 0): "new"})

        self.assertEqual(result, source)
        self.assertEqual(rw.structural, {("p", "a", "", 0)})
        self.assertNotIn(("p", "a", "", 0), rw.applied)

    def test_non_text_tag_is_not_rewritten(self):
        source = '<div class="a">x</div>'
        result, rw = rewrite(source, {("div", "a", "", 0): "new"})

        self.assertEqual(result, source)
        self.assertEqual(rw.structural, {("div", "a", "", 0)})

    def test_absent_signature_is_reported(self):
        source = '<p class="a">only</p>'
        _, rw = rewrite(source, {("p", "a", "", 1): "second"})

        self.assertEqual(rw.absent, {("p", "a", "", 1)})
        self.assertEqual(rw.applied, set())

    def test_scripts_and_styles_pass_through_untouched(self):
        source = (
            "<style>.a{color:#000}</style>"
            '<h2 class="t">Titre</h2>'
            "<script>if (a < b && c > d) { x(); }</script>"
        )
        result, rw = rewrite(source, {("h2", "t", "", 0): "Title"})

        self.assertEqual(
            result,
            "<style>.a{color:#000}</style>"
            '<h2 class="t">Title</h2>'
            "<script>if (a < b && c > d) { x(); }</script>",
        )
        self.assertEqual(rw.rewritten, {("h2", "t", "", 0)})

    def test_count_mismatch_blocks_occurrence_alignment(self):
        # Template lists 3 same-signature spans; the legacy page lists only 2
        # (e.g. a language switcher omitting the current language). Occurrence
        # alignment is unreliable, so nothing is rewritten.
        from collections import Counter

        source = '<span class="l">Français</span><span class="l">Italiano</span>'
        targets = {("span", "l", "", 0): "English", ("span", "l", "", 1): "Français"}
        template_counts = Counter({("span", "l", ""): 3})
        rewriter = SlotRewriter(source, targets, template_counts)
        result = rewriter.rewrite()

        self.assertEqual(result, source)
        self.assertEqual(rewriter.rewritten, set())
        self.assertEqual(rewriter.structural, set(targets))

    def test_matching_counts_allow_alignment(self):
        from collections import Counter

        source = '<span class="l">Old</span><span class="l">Keep</span>'
        targets = {("span", "l", "", 0): "New"}
        template_counts = Counter({("span", "l", ""): 2})
        rewriter = SlotRewriter(source, targets, template_counts)
        result = rewriter.rewrite()

        self.assertEqual(result, '<span class="l">New</span><span class="l">Keep</span>')
        self.assertEqual(rewriter.rewritten, {("span", "l", "", 0)})

    def test_occurrence_index_skips_void_children(self):
        source = '<p class="a">one<img/></p><p class="a">two</p>'
        result, rw = rewrite(source, {("p", "a", "", 1): "TWO"})

        # The <img/> void element must not shift the second <p> occurrence index.
        self.assertEqual(result, '<p class="a">one<img/></p><p class="a">TWO</p>')
        self.assertEqual(rw.rewritten, {("p", "a", "", 1)})


class TemplateBindingsTests(unittest.TestCase):
    def test_collects_content_and_entity_by_signature(self):
        source = (
            '<button class="filter-btn" data-content="local:Q1">Q1</button>'
            '<li><a href="x" data-entity="local:Q2">Q2</a></li>'
            '<span>unbound</span>'
        )
        bindings = template_bindings_from_string(source)

        self.assertEqual(bindings[("button", "filter-btn", "", 0)], "Q1")
        self.assertEqual(bindings[("a", "", "", 0)], "Q2")
        self.assertNotIn(("span", "", "", 0), bindings)


class GeneratorMetaTests(unittest.TestCase):
    def test_meta_injected_after_head_once(self):
        source = "<html><head>\n<title>x</title></head><body></body></html>"
        once = inject_generator_meta(source)
        twice = inject_generator_meta(once)

        self.assertEqual(once.count("Q315 renderer"), 1)
        self.assertEqual(twice, once)
        self.assertLess(once.index("Q315 renderer"), once.index("<title>"))

    def test_existing_meta_is_detected_regardless_of_attribute_order(self):
        source = (
            '<html><head><meta content="Q315 renderer" name="generator"/>'
            "</head><body></body></html>"
        )

        self.assertEqual(inject_generator_meta(source), source)


def template_bindings_from_string(source):
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(source)
        path = Path(handle.name)
    try:
        return template_bindings(path)
    finally:
        path.unlink()


if __name__ == "__main__":
    unittest.main()
