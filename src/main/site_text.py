#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Shared text helpers for static-site HTML processing."""

from __future__ import annotations

from config import TITLE_AUTHOR_VARIANTS


def strip_author_from_title(title: str) -> str:
    """Remove known author-name variants from a title string."""
    updated = title
    for author_variant in TITLE_AUTHOR_VARIANTS:
        updated = updated.replace(f": {author_variant}", "")
        updated = updated.replace(author_variant, "")
    return updated.replace(":", "").strip()
