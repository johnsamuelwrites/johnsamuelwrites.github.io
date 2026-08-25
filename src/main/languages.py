#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The site's language registry: the single source of truth for its languages.

Before this module the set of languages was declared independently in nine
places and they disagreed -- ``translation_config`` still listed German and
Dutch, which the site has never published, and ``blog.py`` iterated a five
language subset that both included languages with no blog and excluded three
that have one. Adding a ninth language meant finding every one of them.

``ORDER`` is the order languages are presented in: English first, then the
languages in the order the travel pages have always used.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    #: Name in English, as used by generated metadata and search indexes.
    english_name: str
    #: Name in the language itself, as shown to a reader in a language switcher.
    endonym: str


#: Every language the site publishes, in presentation order.
LANGUAGES: tuple[Language, ...] = (
    Language("en", "English", "English"),
    Language("fr", "Francais", "Français"),
    Language("ml", "Malayalam", "മലയാളം"),
    Language("pa", "Punjabi", "ਪੰਜਾਬੀ"),
    Language("hi", "Hindi", "हिन्दी"),
    Language("pt", "Portuguese", "Português"),
    Language("es", "Spanish", "Español"),
    Language("it", "Italian", "Italiano"),
)

#: The language content is authored in and translated from.
SOURCE = "en"

ORDER: tuple[str, ...] = tuple(language.code for language in LANGUAGES)
TARGETS: tuple[str, ...] = tuple(code for code in ORDER if code != SOURCE)
ENGLISH_NAMES: dict[str, str] = {l.code: l.english_name for l in LANGUAGES}
ENDONYMS: dict[str, str] = {l.code: l.endonym for l in LANGUAGES}


def is_supported(code: str) -> bool:
    return code in ENGLISH_NAMES
