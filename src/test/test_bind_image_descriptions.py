#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Binding an image description must never point at the wrong photograph."""

import sys
import tempfile
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))
sys.path.insert(0, str(MAIN / "abstract"))

from abstract.bind_image_descriptions import images, write_binding


def page(source):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(source)
        return Path(handle.name)


class WriteBindingTests(unittest.TestCase):
    IMAGE = '<html><body><img class="photo-image" alt="" src="x.jpg" /></body></html>'
    KEY = ("img", "photo-image", "", 0)

    def test_the_binding_is_written_onto_the_addressed_image(self):
        path = page(self.IMAGE)
        try:
            self.assertTrue(write_binding(path, self.KEY, "Q123"))
            self.assertIn('data-content-alt="local:Q123"', path.read_text(encoding="utf-8"))
        finally:
            path.unlink()

    def test_writing_twice_does_not_bind_twice(self):
        path = page(self.IMAGE)
        try:
            write_binding(path, self.KEY, "Q123")
            self.assertFalse(write_binding(path, self.KEY, "Q999"))
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("data-content-alt"), 1)
            self.assertIn("local:Q123", text)
        finally:
            path.unlink()

    def test_the_src_and_alt_survive_the_edit(self):
        path = page(self.IMAGE)
        try:
            write_binding(path, self.KEY, "Q123")
            text = path.read_text(encoding="utf-8")
            self.assertIn('src="x.jpg"', text)
            self.assertIn('alt=""', text)
            self.assertTrue(text.rstrip().endswith("</body></html>"))
        finally:
            path.unlink()

    def test_a_signature_that_is_not_an_image_is_refused(self):
        path = page('<html><body><p class="photo-image">text</p></body></html>')
        try:
            self.assertFalse(write_binding(path, self.KEY, "Q123"))
            self.assertNotIn("data-content-alt", path.read_text(encoding="utf-8"))
        finally:
            path.unlink()

    def test_the_second_image_is_addressed_by_its_own_occurrence(self):
        path = page(
            '<html><body><img class="p" alt="" src="1.jpg" />'
            '<img class="p" alt="" src="2.jpg" /></body></html>'
        )
        try:
            self.assertTrue(write_binding(path, ("img", "p", "", 1), "Q7"))
            text = path.read_text(encoding="utf-8")
            first, second = text.split("<img")[1:3]
            self.assertNotIn("data-content-alt", first)
            self.assertIn("data-content-alt", second)
        finally:
            path.unlink()


class ImageParsingTests(unittest.TestCase):
    def test_a_self_closing_image_is_seen(self):
        path = page('<img class="a" alt="Trees" src="x" />')
        try:
            found = images(path)
            self.assertEqual(found[("img", "a", "", 0)], ("Trees", "x", ""))
        finally:
            path.unlink()

    def test_an_existing_binding_is_reported(self):
        path = page('<img class="a" alt="" src="x" data-content-alt="local:Q5" />')
        try:
            self.assertEqual(images(path)[("img", "a", "", 0)][2], "Q5")
        finally:
            path.unlink()

    def test_occurrence_counting_includes_non_image_elements(self):
        """The signature counts per (tag, class, role), matching the renderer."""
        path = page('<div class="a"></div><img class="a" alt="" src="x" />')
        try:
            self.assertIn(("img", "a", "", 0), images(path))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
