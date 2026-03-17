#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Shared translation parsing rules."""

from __future__ import annotations

SKIP_TRANSLATION_TAGS = {"script", "style", "code", "pre"}

TRANSLATABLE_ATTRIBUTES = {
    "title",
    "alt",
    "placeholder",
    "aria-label",
    "aria-description",
    "content",
}

NO_TRANSLATE_CLASS = "no-translate"

TRANSLATABLE_META_NAMES = {"description", "keywords"}
