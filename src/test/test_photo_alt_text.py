#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Every photograph on a published page announces itself.

An ``alt=""`` marks an image as decorative, so a screen reader skips it
entirely. That is right for the spacer graphics and the frame ornaments, and
wrong for a photograph, which is the entire content of the card it sits in.

The Q315 abstract sources are deliberately exempt: they are language-independent
documents, alt text is language-specific, and ``render_page.py`` rewrites text
nodes rather than attributes, so there is nowhere for a translated alt to be
bound. Their language pages carry it instead, and those are what this asserts.
"""

import re
import sys
import unittest
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main"
sys.path.insert(0, str(MAIN))

from languages import ORDER
from paths import REPO_ROOT

PHOTO_IMAGE = re.compile(r'<img\b[^>]*\bclass="[^"]*\bphoto-image\b[^"]*"[^>]*>')
ALT = re.compile(r'\balt="([^"]*)"')
SRC = re.compile(r'\bsrc="([^"]*)"')


def undescribed(language: str) -> list[tuple[str, str]]:
    """(page, image) for every photograph on a language page with no alt text."""
    found = []
    for page in sorted((REPO_ROOT / language).glob("**/*.html")):
        text = page.read_text(encoding="utf-8", errors="replace")
        for tag in PHOTO_IMAGE.findall(text):
            alt = ALT.search(tag)
            if alt and alt.group(1).strip():
                continue
            src = SRC.search(tag)
            found.append(
                (
                    str(page.relative_to(REPO_ROOT)),
                    src.group(1).rsplit("/", 1)[-1] if src else "?",
                )
            )
    return found


class PhotoAltTextTests(unittest.TestCase):
    def test_every_language_describes_every_photograph(self):
        for language in ORDER:
            with self.subTest(language=language):
                missing = undescribed(language)
                self.assertEqual(
                    missing,
                    [],
                    f"{len(missing)} photograph(s) in {language} carry no alt text",
                )

    def test_the_languages_agree_on_how_many_photographs_they_show(self):
        counts = {}
        for language in ORDER:
            total = 0
            for page in (REPO_ROOT / language).glob("**/*.html"):
                total += len(
                    PHOTO_IMAGE.findall(page.read_text(encoding="utf-8", errors="replace"))
                )
            counts[language] = total
        self.assertEqual(
            len(set(counts.values())), 1, f"photograph counts differ: {counts}"
        )


if __name__ == "__main__":
    unittest.main()
