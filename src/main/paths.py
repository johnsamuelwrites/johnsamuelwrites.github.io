#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Shared path helpers for static-site tooling."""

from __future__ import annotations

from pathlib import Path

from config import SEARCH_INDEX_FILENAME

SRC_MAIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_MAIN_DIR.parents[1]


def repo_root() -> Path:
    """Return the repository root."""
    return REPO_ROOT


def language_root(language_code: str) -> Path:
    """Return the root directory for a language tree."""
    return REPO_ROOT / language_code


def search_index_path(language_code: str) -> Path:
    """Return the output path for a language search index."""
    return language_root(language_code) / SEARCH_INDEX_FILENAME


def to_repo_relative(path: str | Path) -> Path:
    """Return a path relative to the repository root when possible."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        return candidate.relative_to(REPO_ROOT)
    except ValueError:
        return candidate


def repo_url_for(path: str | Path) -> str:
    """Build a site-relative URL rooted at the repository."""
    relative = to_repo_relative(path)
    return str(relative).replace("\\", "/")
