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
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
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

EXCLUDED_DIRECTORIES: tuple[str, ...] = (
    "templates",
    "analysis",
    "src",
    "ui",
    ".git",
    ".github",
    "node_modules",
)

ALLOWED_UNREFERENCED_HTML_FILES: tuple[str, ...] = (
    "404.html",
    "license.html",
    "blog/report.html",
    "en/slides/2017/Akademy/html/kde-wikidata.html",
    "Q315/Q3062/Q3021.html",
    "Q315/Q3062/Q3061.html",
    "Q315/Q3636/Q3646.html",
)

SEARCH_INDEX_FILENAME = "search-index.json"

TITLE_AUTHOR_VARIANTS: tuple[str, ...] = (
    "John Samuel",
    "john samuel",
    "johnsamuel",
)
