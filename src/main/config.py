#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Shared configuration for the static-site tooling."""

from __future__ import annotations

SITE_URL = "https://johnsamuel.info"
SITE_AUTHOR = "John Samuel"

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "fr": "Francais",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "hi": "Hindi",
}

CATEGORY_MAP: dict[str, str] = {
    "research": "research",
    "teaching": "teaching",
    "writings": "writings",
    "linguistics": "linguistics",
    "photography": "photography",
    "travel": "travel",
    "blog": "blog",
    "projects": "projects",
    "programming": "programming",
}

EXCLUDED_DIRECTORIES: tuple[str, ...] = ("templates", "analysis", ".git", "node_modules")

SEARCH_INDEX_FILENAME = "search-index.json"

TITLE_AUTHOR_VARIANTS: tuple[str, ...] = (
    "John Samuel",
    "john samuel",
    "johnsamuel",
)
