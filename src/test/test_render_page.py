import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from collections import Counter

from abstract.render_page import (
    BINDABLE_ATTRIBUTES,
    SlotRewriter,
    inject_generator_meta,
    template_bindings,
    template_slots,
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


class AttributeSlotTests(unittest.TestCase):
    """`alt` is content, and content belongs to the abstract layer.

    The renderer could only ever rewrite text nodes, so an image description --
    the one thing a reader who cannot see the image depends on -- stayed a
    literal in each language page. `data-content-alt` binds it like any label.
    """

    IMAGE = '<img class="photo-image" alt="" src="x.jpg" />'
    SLOT = (("img", "photo-image", "", 0), "alt")

    def rewrite(self, source, attributes, counts=None):
        rewriter = SlotRewriter(source, {}, counts, attributes)
        return rewriter.rewrite(), rewriter

    def test_a_bound_attribute_is_written(self):
        result, rw = self.rewrite(self.IMAGE, {self.SLOT: "Arbres à Lyon"})
        self.assertIn('alt="Arbres à Lyon"', result)
        self.assertEqual(rw.attributes_rewritten, {self.SLOT})

    def test_a_matching_value_is_left_alone(self):
        source = '<img class="photo-image" alt="Trees" src="x.jpg" />'
        result, rw = self.rewrite(source, {self.SLOT: "Trees"})
        self.assertEqual(result, source)
        self.assertEqual(rw.attributes_rewritten, set())
        self.assertEqual(rw.attributes_applied, {self.SLOT})

    def test_quotes_in_a_description_cannot_break_the_attribute(self):
        result, _ = self.rewrite(self.IMAGE, {self.SLOT: 'A "quoted" caption'})
        self.assertIn("&quot;quoted&quot;", result)
        self.assertEqual(result.count('alt="'), 1)

    def test_other_attributes_and_the_src_are_untouched(self):
        result, _ = self.rewrite(self.IMAGE, {self.SLOT: "Trees"})
        self.assertIn('src="x.jpg"', result)
        self.assertIn('class="photo-image"', result)

    def test_a_count_mismatch_refuses_to_write(self):
        """Occurrence N is not the same image on both sides; skip, never guess."""
        counts = Counter({("img", "photo-image", ""): 2})
        result, rw = self.rewrite(self.IMAGE, {self.SLOT: "Trees"}, counts)
        self.assertEqual(result, self.IMAGE)
        self.assertEqual(rw.attributes_rewritten, set())

    def test_an_absent_attribute_is_reported_not_invented(self):
        source = '<img class="photo-image" src="x.jpg" />'
        _result, rw = self.rewrite(source, {self.SLOT: "Trees"})
        self.assertIn(self.SLOT, rw.attributes_absent)

    def test_a_text_slot_and_an_attribute_slot_coexist(self):
        source = '<figure class="f"><img class="i" alt="" src="x" /></figure><p class="c">old</p>'
        rewriter = SlotRewriter(
            source,
            {("p", "c", "", 0): "nouveau"},
            None,
            {(("img", "i", "", 0), "alt"): "description"},
        )
        result = rewriter.rewrite()
        self.assertIn('alt="description"', result)
        self.assertIn("<p class=\"c\">nouveau</p>", result)

    def test_only_prose_attributes_are_bindable(self):
        """Binding src or href would have the renderer rewrite a URL from a label."""
        self.assertIn("alt", BINDABLE_ATTRIBUTES)
        self.assertNotIn("src", BINDABLE_ATTRIBUTES)
        self.assertNotIn("href", BINDABLE_ATTRIBUTES)


class AttributeBindingDiscoveryTests(unittest.TestCase):
    def slots(self, source):
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(source)
            path = Path(handle.name)
        try:
            return template_slots(path)
        finally:
            path.unlink()

    def test_a_self_closing_image_is_discovered(self):
        _text, _counts, attributes = self.slots(
            '<img class="photo-image" data-content-alt="local:Q9" alt="" />'
        )
        self.assertEqual(attributes[(("img", "photo-image", "", 0), "alt")], "Q9")

    def test_an_unbindable_attribute_is_ignored(self):
        _text, _counts, attributes = self.slots(
            '<img class="i" data-content-src="local:Q9" alt="" />'
        )
        self.assertEqual(attributes, {})

    def test_text_and_attribute_bindings_are_kept_apart(self):
        text, _counts, attributes = self.slots(
            '<figcaption data-content="local:Q1">Q1</figcaption>'
            '<img class="i" data-content-alt="local:Q2" alt="" />'
        )
        self.assertEqual(text[("figcaption", "", "", 0)], "Q1")
        self.assertEqual(attributes[(("img", "i", "", 0), "alt")], "Q2")
        self.assertNotIn(("img", "i", "", 0), text)


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
