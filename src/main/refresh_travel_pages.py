#!/usr/bin/env python3
"""Refresh translated travel pages from the modern English HTML shell.

This script is deliberately file-based: it uses the existing translated travel
pages as the source of translated labels, captions, and page mappings, then
copies the modern English page structure/CSS into selected target languages.
It also rebuilds the travel language selector so Spanish, Italian, and
Portuguese pages link to themselves and to each other.
"""

from __future__ import annotations

import argparse
import html
import os
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from paths import REPO_ROOT


from languages import ENDONYMS as LANGUAGE_NAMES

from languages import ORDER as LANGUAGE_ORDER



INDIC_LANGS = ("ml", "pa", "hi")
LATIN_TARGET_LANGS = ("it", "pt", "es")
REFRESH_SELECTOR_LANGS = LANGUAGE_ORDER



PLACE_NAMES_CSV = REPO_ROOT / "data/translations/place-names.csv"
PAGE_SLUGS_CSV = REPO_ROOT / "data/translations/page-slugs.csv"
UI_LABELS_CSV = REPO_ROOT / "data/translations/ui-labels.csv"


def _keyed_by_english(path: Path, key_column: str = "en") -> dict[str, dict[str, str]]:
    """Read a `<key>, <language>...` CSV into ``{english: {language: text}}``.

    An empty cell means "this language uses the English form" and is left out, so
    a caller's ``.get(language)`` still falls back the way it always did. City
    names rely on that: they are transliterated for ml/pa/hi and kept as-is in
    the Latin-script languages.
    """
    table: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            table[row[key_column]] = {
                language: row[language]
                for language in LANGUAGE_ORDER
                if language != "en" and row.get(language)
            }
    return table


def load_place_names(path: Path = PLACE_NAMES_CSV) -> tuple[dict, dict]:
    """Return the country and city name tables."""
    countries: dict[str, dict[str, str]] = {}
    cities: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            target = {"country": countries, "city": cities}.get(row["kind"])
            if target is None:
                raise ValueError(f"{path}: unknown kind {row['kind']!r}")
            target[row["en"]] = {
                language: row[language]
                for language in LANGUAGE_ORDER
                if language != "en" and row.get(language)
            }
    return countries, cities


def load_ui_labels(path: Path = UI_LABELS_CSV) -> dict[str, dict[str, str]]:
    """Return ``{language: {key: label}}`` -- the shape the page builders want."""
    labels: dict[str, dict[str, str]] = {language: {} for language in LANGUAGE_ORDER}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            for language in LANGUAGE_ORDER:
                # An empty cell means this language has no wording of its own;
                # leaving the key out keeps a caller's .get() fallback working.
                if row[language]:
                    labels[language][row["key"]] = row[language]
    return labels


COUNTRY_NAME_TRANSLATIONS, CITY_NAME_TRANSLATIONS = load_place_names()
PAGE_SLUG_TRANSLATIONS = _keyed_by_english(PAGE_SLUGS_CSV)
COUNTRY_PAGE_LABELS = load_ui_labels()


CITY_PAGE_LABELS = {
    lang: {
        "photography": labels["photography"],
        "site_tagline": labels["site_tagline"],
        "home": labels["home"],
        "travel": labels["travel"],
        "credits": labels["credits"],
        "footer": "{city} - {country}",
    }
    for lang, labels in COUNTRY_PAGE_LABELS.items()
}




EN_TRAVEL_PAGES = {"drawings", "index", "miles-to-go", "pilgrimage"}






# Photo alt text and captions are the one part of the travel vocabulary that is
# genuinely translated rather than a proper noun, so it lives in a reviewable CSV
# instead of in this file: a translator can work on it without touching Python,
# and a new language is a new column rather than 296 edits.
IMAGE_DESCRIPTIONS_CSV = REPO_ROOT / "data/translations/image-descriptions.csv"


def load_image_descriptions(
    path: Path = IMAGE_DESCRIPTIONS_CSV,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Return the ``alt`` and ``caption`` lookup tables, keyed by English text."""
    tables: dict[str, dict[str, dict[str, str]]] = {"alt": {}, "caption": {}}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            table = tables.get(row["table"])
            if table is None:
                raise ValueError(f"{path}: unknown table {row['table']!r}")
            table[row["en"]] = {
                language: row[language]
                for language in LANGUAGE_ORDER
                if language != "en" and row.get(language)
            }
    return tables["alt"], tables["caption"]


PHOTO_ALT_TRANSLATIONS, PHOTO_CAPTION_TRANSLATIONS = load_image_descriptions()


PATH_SEGMENTS_CSV = REPO_ROOT / "data/translations/path-segments.csv"


def load_path_segments(path: Path = PATH_SEGMENTS_CSV) -> dict[str, dict[str, Path]]:
    """Return ``{key: {language: directory}}`` for the translated page roots."""
    segments: dict[str, dict[str, Path]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            segments[row["key"]] = {
                language: Path(row[language]) for language in LANGUAGE_ORDER
            }
    return segments


_PATH_SEGMENTS = load_path_segments()
TRAVEL_DIRS = _PATH_SEGMENTS["travel"]
TRAVEL_INDEX_DIRS = _PATH_SEGMENTS["travel_index"]


def escape_image_text(text: str, in_attr: bool = False) -> str:
    """Escape only what HTML strictly requires, preserving accents/apostrophes."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if in_attr:
        text = text.replace('"', "&quot;")
    return text


def translate_image_text(text: str, lang: str) -> str:
    if lang == "en":
        return text
    key = text.strip()
    for table in (PHOTO_ALT_TRANSLATIONS, PHOTO_CAPTION_TRANSLATIONS):
        translated = table.get(key, {}).get(lang)
        if translated:
            return translated
    return text


def translate_image_descriptions(content: str, lang: str) -> str:
    """Translate gallery photo alt text and photo-location captions in place."""
    if lang == "en":
        return content

    def replace_alt(match: re.Match[str]) -> str:
        translated = translate_image_text(html.unescape(match.group(2)), lang)
        return f"{match.group(1)}{escape_image_text(translated, in_attr=True)}{match.group(3)}"

    content = re.sub(
        r'(<img\b[^>]*\balt=")([^"]*)("[^>]*\bclass="photo-image")',
        replace_alt,
        content,
    )

    def replace_caption(match: re.Match[str]) -> str:
        translated = translate_image_text(strip_tags(match.group(2)), lang)
        return f"{match.group(1)}{escape_image_text(translated)}{match.group(3)}"

    return re.sub(
        r'(<h4 class="photo-location">)(.*?)(</h4>)',
        replace_caption,
        content,
        flags=re.DOTALL,
    )


MANUAL_PAGE_GROUPS = [
    {
        "en": "en/photography/an-amateur.html",
        "fr": "fr/voyages/un-amateur.html",
        "ml": "ml/യാത്രകൾ/അമച്വർ-ഫോട്ടോഗ്രാഫർ.html",
        "pa": "pa/ਯਾਤਰਾ/ਇੱਕ-ਸ਼ੁਕੀਨ.html",
        "hi": "hi/यात्रा/एक-शौकिया-फोटोग्राफर.html",
        "pt": "pt/viagens/um-amador.html",
        "es": "es/viajes/un-aficionado.html",
        "it": "it/viaggi/un-dilettante.html",
    },
    {
        "en": "en/travel/drawings.html",
        "fr": "fr/voyages/dessins.html",
        "ml": "ml/യാത്രകൾ/ചിത്രങ്ങൾ.html",
        "pa": "pa/ਯਾਤਰਾ/ਚਿੱਤਰਕਾਰੀ.html",
        "hi": "hi/यात्रा/चित्र.html",
        "pt": "pt/viagens/desenhos.html",
        "es": "es/viajes/dibujos.html",
        "it": "it/viaggi/disegni.html",
    },
    {
        "en": "en/photography/celebrations.html",
        "fr": "fr/voyages/festivités.html",
        "ml": "ml/യാത്രകൾ/ആഘോഷങ്ങൾ.html",
        "pa": "pa/ਯਾਤਰਾ/ਜਸ਼ਨ.html",
        "hi": "hi/यात्रा/समारोह.html",
        "pt": "pt/viagens/celebrações.html",
        "es": "es/viajes/celebraciones.html",
        "it": "it/viaggi/celebrazioni.html",
    },
    {
        "en": "en/travel/miles-to-go.html",
        "fr": "fr/voyages/kilomètres-à-parcourir.html",
        "ml": "ml/യാത്രകൾ/മൈലുകൾ-പോകണം.html",
        "pa": "pa/ਯਾਤਰਾ/ਸਫ਼ਰ-ਕਰਨ-ਲਈ-ਕਿਲੋਮੀਟਰ-ਹਨ.html",
        "hi": "hi/यात्रा/कई-किलोमीटर-की-यात्रा-करनी-है.html",
        "pt": "pt/viagens/milhas-por-percorrer.html",
        "es": "es/viajes/millas-por-recorrer.html",
        "it": "it/viaggi/miglia-da-percorrere.html",
    },
    {
        "en": "en/travel/pilgrimage.html",
        "fr": "fr/voyages/pèlerinage.html",
        "ml": "ml/യാത്രകൾ/തീർത്ഥാടനം.html",
        "pa": "pa/ਯਾਤਰਾ/ਤੀਰਥ-ਯਾਤਰਾ.html",
        "hi": "hi/यात्रा/तीर्थयात्रा.html",
        "pt": "pt/viagens/peregrinação.html",
        "es": "es/viajes/peregrinación.html",
        "it": "it/viaggi/pellegrinaggio.html",
    },
    {
        "en": "en/photography/software.html",
        "fr": "fr/voyages/logiciel.html",
        "ml": "ml/യാത്രകൾ/സോഫ്‌റ്റ്‌വെയർ.html",
        "pa": "pa/ਯਾਤਰਾ/ਸਾਫਟਵੇਅਰ.html",
        "hi": "hi/यात्रा/सॉफ़्टवेयर.html",
        "pt": "pt/viagens/software.html",
        "es": "es/viajes/software.html",
        "it": "it/viaggi/software.html",
    },
    {
        "en": "en/photography/sunset.html",
        "fr": "fr/voyages/coucher-du-soleil.html",
        "ml": "ml/യാത്രകൾ/സൂര്യാസ്തമയം.html",
        "pa": "pa/ਯਾਤਰਾ/ਸੂਰਜ-ਡੁੱਬਣ.html",
        "hi": "hi/यात्रा/सूर्यास्त.html",
        "pt": "pt/viagens/pôr-do-sol.html",
        "es": "es/viajes/atardecer.html",
        "it": "it/viaggi/tramonto.html",
    },
]


@dataclass
class GalleryItem:
    image_src: str
    label: str
    href: str = ""
    image_alt: str = ""


@dataclass
class GallerySection:
    title: str
    items: list[GalleryItem] = field(default_factory=list)


@dataclass
class OldTravelPage:
    path: Path
    lang: str
    title: str
    heading: str
    nav_labels: dict[str, tuple[str, str]]
    sections: list[GallerySection]
    content_html: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(content, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def normalize_href(href: str, base_file: Path) -> str | None:
    if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    return (base_file.parent / html.unescape(href)).resolve().relative_to(REPO_ROOT).as_posix()


def current_lang_for_path(path: Path) -> str | None:
    rel = repo_rel(path)
    return lang_for_repo_path(rel)


def lang_for_repo_path(rel: str) -> str | None:
    for lang, directory in TRAVEL_DIRS.items():
        if rel.startswith(directory.as_posix() + "/"):
            return lang
    for lang, directory in TRAVEL_INDEX_DIRS.items():
        if rel.startswith(directory.as_posix() + "/"):
            return lang
    return None


def extract_lang_links(content: str, path: Path) -> dict[str, str]:
    links: dict[str, str] = {}
    for match in re.finditer(
        r'<li[^>]*id="((?:[a-z]{2}|q315))page"[^>]*>.*?<a[^>]*href="([^"]+)"',
        content,
        flags=re.DOTALL,
    ):
        lang, href = match.groups()
        normalized = normalize_href(href, path)
        if normalized:
            actual_lang = lang_for_repo_path(normalized)
            if actual_lang and actual_lang != lang:
                continue
            links[lang] = normalized

    current_lang = current_lang_for_path(path)
    if current_lang:
        links[current_lang] = repo_rel(path)
    return links


def english_page_path(slug: str) -> str:
    directory = TRAVEL_INDEX_DIRS["en"] if slug in EN_TRAVEL_PAGES else TRAVEL_DIRS["en"]
    return (directory / f"{slug}.html").as_posix()


def translated_page_path(slug: str, lang: str) -> str:
    if lang == "en":
        return english_page_path(slug)
    translated_slug = PAGE_SLUG_TRANSLATIONS[slug][lang]
    return (TRAVEL_INDEX_DIRS[lang] / f"{translated_slug}.html").as_posix()


def page_translation_groups() -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    for slug, translations in PAGE_SLUG_TRANSLATIONS.items():
        group = {"en": english_page_path(slug)}
        group.update(
            {
                lang: translated_page_path(slug, lang)
                for lang in LANGUAGE_ORDER
                if lang != "en" and lang in translations
            }
        )
        groups.append(group)
    return groups


def country_translation_groups() -> list[dict[str, str]]:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    groups: list[dict[str, str]] = []
    for english_name, translations in COUNTRY_NAME_TRANSLATIONS.items():
        names = {"en": english_name} | translations
        group: dict[str, str] = {}
        for lang in LANGUAGE_ORDER:
            directory = TRAVEL_DIRS[lang] / country_dir_slugs[lang]
            path = directory / f"{names[lang]}.html"
            rel = path.as_posix()
            if (REPO_ROOT / rel).exists():
                group[lang] = rel
        if group:
            groups.append(group)
    return groups


def expected_country_translation_groups() -> list[dict[str, str]]:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    groups: list[dict[str, str]] = []
    for english_name, translations in COUNTRY_NAME_TRANSLATIONS.items():
        names = {"en": english_name} | translations
        groups.append(
            {
                lang: (TRAVEL_DIRS[lang] / country_dir_slugs[lang] / f"{names[lang]}.html").as_posix()
                for lang in LANGUAGE_ORDER
            }
        )
    return groups


def expected_translation_groups() -> list[dict[str, str]]:
    return page_translation_groups() + expected_country_translation_groups() + expected_city_translation_groups()


def country_page_path(english_name: str, lang: str) -> str:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    names = {"en": english_name} | COUNTRY_NAME_TRANSLATIONS[english_name]
    return (TRAVEL_DIRS[lang] / country_dir_slugs[lang] / f"{names[lang]}.html").as_posix()


def city_dir_slug(lang: str) -> str:
    return "cities" if lang == "en" else PAGE_SLUG_TRANSLATIONS["cities"][lang]


def city_country_dir_name(english_country: str, lang: str) -> str:
    return english_country if lang == "en" else COUNTRY_NAME_TRANSLATIONS[english_country][lang]


def translated_city_name(city_name: str, lang: str) -> str:
    """The city's name in one language, falling back to its own name.

    Any language may have an exonym -- French writes Antwerp as *Anvers* and
    Venice as *Venise* -- so this consults the table for every language rather
    than only the ones that transliterate. A city with no entry for a language
    keeps its own name, which is what the Latin-script pages mostly do.
    """
    return CITY_NAME_TRANSLATIONS.get(city_name, {}).get(lang, city_name)


def translated_city_filename(city_filename: str, lang: str) -> str:
    city_name = Path(city_filename).stem
    translated_name = translated_city_name(city_name, lang)
    return f"{translated_name}.html"


def rewrite_local_city_hrefs(content: str, lang: str) -> str:
    if lang not in INDIC_LANGS:
        return content

    def rewrite(match: re.Match[str]) -> str:
        href = html.unescape(match.group(1))
        if "/" in href or href.startswith(("#", "mailto:", "tel:", "http://", "https://")):
            return match.group(0)
        city_name = Path(href).stem
        if city_name not in CITY_NAME_TRANSLATIONS:
            return match.group(0)
        return f'{match.group(1)[:0]}href="{html.escape(translated_city_filename(href, lang))}"'

    return re.sub(r'href="([^"]+\.html)"', rewrite, content)


def city_page_path(english_country: str, city_filename: str, lang: str) -> str:
    filename = translated_city_filename(city_filename, lang)
    return (
        TRAVEL_DIRS[lang]
        / city_dir_slug(lang)
        / city_country_dir_name(english_country, lang)
        / filename
    ).as_posix()


def first_image_src(path: Path) -> str:
    match = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', read_text(path), flags=re.DOTALL)
    return html.unescape(match.group(1)) if match else ""


def expected_city_translation_groups() -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    english_root = REPO_ROOT / TRAVEL_DIRS["en"] / city_dir_slug("en")
    if not english_root.exists():
        return groups
    for source_path in sorted(english_root.glob("*/*.html")):
        english_country = source_path.parent.name
        if english_country not in COUNTRY_NAME_TRANSLATIONS:
            continue
        city_filename = source_path.name
        group = {
            lang: city_page_path(english_country, city_filename, lang)
            for lang in LANGUAGE_ORDER
        }
        groups.append(group)
    return groups


def city_translation_groups() -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    for expected_group in expected_city_translation_groups():
        group = {
            lang: target
            for lang, target in expected_group.items()
            if (REPO_ROOT / target).exists()
        }
        if group:
            groups.append(group)
    return groups


def is_country_detail_path(path: Path) -> bool:
    rel = repo_rel(path)
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    return any(
        rel.startswith((TRAVEL_DIRS[lang] / country_dir_slugs[lang]).as_posix() + "/")
        for lang in LANGUAGE_ORDER
    )


def is_city_detail_path(path: Path) -> bool:
    rel = repo_rel(path)
    return any(
        rel.startswith((TRAVEL_DIRS[lang] / city_dir_slug(lang)).as_posix() + "/")
        for lang in LANGUAGE_ORDER
    )


def collect_page_groups() -> dict[str, dict[str, str]]:
    groups: list[dict[str, str]] = []
    groups.extend(page_translation_groups())
    groups.extend(country_translation_groups())
    groups.extend(city_translation_groups())
    for manual_group in MANUAL_PAGE_GROUPS:
        groups.append(dict(manual_group))
    for directory in set(TRAVEL_DIRS.values()) | set(TRAVEL_INDEX_DIRS.values()):
        absolute_dir = REPO_ROOT / directory
        if not absolute_dir.exists():
            continue
        for path in absolute_dir.rglob("*.html"):
            links = extract_lang_links(read_text(path), path)
            if not links:
                continue
            current_rel = repo_rel(path)
            current_matches = [
                index
                for index, group in enumerate(groups)
                if current_rel in group.values()
            ]
            matching = current_matches or [
                index
                for index, group in enumerate(groups)
                if set(group.values()) & set(links.values())
            ]
            if not matching:
                groups.append(dict(links))
                continue
            primary = matching[0]
            for lang, target in links.items():
                if current_matches and lang not in groups[primary] and target != current_rel:
                    continue
                groups[primary].setdefault(lang, target)
            for duplicate in reversed(matching[1:]):
                groups[primary].update(groups[duplicate])
                del groups[duplicate]

    groups.extend(page_translation_groups())
    groups.extend(country_translation_groups())
    groups.extend(city_translation_groups())

    keyed: dict[str, dict[str, str]] = {}
    for group in groups:
        key = group.get("en") or group.get("fr") or sorted(group.values())[0]
        keyed.setdefault(key, {}).update(group)
    for group in page_translation_groups() + country_translation_groups() + city_translation_groups():
        key = group.get("en") or group.get("fr") or sorted(group.values())[0]
        keyed[key] = dict(group)
    return keyed


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(" ".join(text.split())).strip()


def extract_attr(fragment: str, attr: str) -> str:
    match = re.search(rf'{attr}="([^"]*)"', fragment)
    return html.unescape(match.group(1)) if match else ""


def extract_nav_labels(content: str) -> dict[str, tuple[str, str]]:
    labels: dict[str, tuple[str, str]] = {}
    for match in re.finditer(
        r'<li[^>]*typeof="ListItem"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?'
        r'<span[^>]*property="name"[^>]*>(.*?)</span>',
        content,
        flags=re.DOTALL,
    ):
        href, label = match.groups()
        clean_label = strip_tags(label)
        if clean_label:
            labels[href] = (href, clean_label)
    return labels


def parse_old_page(path: Path, lang: str) -> OldTravelPage:
    content = read_text(path)
    title_match = re.search(r"<title>(.*?)</title>", content, flags=re.DOTALL)
    title = strip_tags(title_match.group(1)) if title_match else ""
    content_match = re.search(
        r'<div class="content">(.*?)(?:</div>\s*<br\s*/?>\s*</div>|</div>\s*</body>)',
        content,
        flags=re.DOTALL,
    )
    if content_match:
        content_html = content_match.group(1).strip()
    else:
        modern_match = re.search(
            r'<section class="main-content">\s*<article class="content-card">\s*(.*?)\s*</article>\s*</section>',
            content,
            flags=re.DOTALL,
        )
        content_html = modern_match.group(1).strip() if modern_match else ""
    content_html = re.sub(r'<section id="langsection">.*?</section>', "", content_html, flags=re.DOTALL).strip()
    content_html = re.sub(r"\s*</div>\s*$", "", content_html).strip()
    body = content_html
    heading_match = re.search(r"<h2[^>]*>(.*?)</h2>", body, flags=re.DOTALL)
    heading = strip_tags(heading_match.group(1)) if heading_match else title.split(":")[1].strip() if ":" in title else title

    sections: list[GallerySection] = []
    current = GallerySection(COUNTRY_PAGE_LABELS[lang].get("highlights", "Highlights"))
    for token in re.finditer(r"<h3[^>]*>(.*?)</h3>|<li[^>]*>(.*?)</li>", body, flags=re.DOTALL):
        section_title, item_html = token.groups()
        if section_title is not None:
            if current.items:
                sections.append(current)
            current = GallerySection(strip_tags(section_title))
            continue
        if not item_html:
            continue
        img_match = re.search(r"<img\b[^>]*>", item_html, flags=re.DOTALL)
        if not img_match:
            continue
        img_html = img_match.group(0)
        src = extract_attr(img_html, "src")
        label = strip_tags(item_html[img_match.end() :])
        href_match = re.search(r'<a[^>]*href="([^"]+)"', item_html, flags=re.DOTALL)
        href = html.unescape(href_match.group(1)) if href_match else ""
        alt = extract_attr(img_html, "alt") or label
        if src and label:
            current.items.append(GalleryItem(src, label, href, alt))
    if current.items:
        sections.append(current)

    return OldTravelPage(path, lang, title, heading, extract_nav_labels(content), sections, content_html)


def replace_one(pattern: str, replacement: str, content: str, flags: int = re.DOTALL) -> str:
    return re.sub(pattern, replacement, content, count=1, flags=flags)


def find_card_templates(content: str) -> list[str]:
    matches = re.findall(r"(<article\b.*?</article>)", content, flags=re.DOTALL)
    if not matches:
        raise ValueError("Could not find a gallery card template")
    return matches


def render_card(template: str, item: GalleryItem) -> str:
    card = re.sub(r'(<img\b[^>]*\balt=")[^"]*(")', rf"\g<1>{html.escape(item.image_alt or item.label)}\2", template, count=1)
    card = re.sub(r"(<h4\b[^>]*>)(.*?)(</h4>)", rf"\g<1>{html.escape(item.label)}\3", card, count=1, flags=re.DOTALL)
    return card


def render_gallery(content: str, old_page: OldTravelPage) -> str:
    card_templates = find_card_templates(content)
    card_index = 0
    rendered_sections = []
    for section in old_page.sections:
        cards = []
        for item in section.items:
            template = card_templates[min(card_index, len(card_templates) - 1)]
            cards.append(render_card(template, item))
            card_index += 1
        cards_html = "\n".join(cards)
        rendered_sections.append(
            f'''                <div class="region-section">
                    <h3 class="region-title">{html.escape(section.title)}</h3>
                    <div class="gallery-grid">
{cards_html}
                    </div>
                </div>'''
        )
    gallery_inner = "\n\n".join(rendered_sections)
    return re.sub(
        r'(<section class="[^"]*gallery[^"]*">\s*)(.*?)(\s*</section>\s*<!-- Footer|\s*</section>\s*<footer)',
        lambda m: f"{m.group(1)}\n{gallery_inner}\n\n            {m.group(3).lstrip()}",
        content,
        count=1,
        flags=re.DOTALL,
    )


def source_index_image_map(source_content: str, source_path: Path) -> dict[str, str]:
    source_images: dict[str, str] = {}
    for match in re.finditer(
        r'<a href="([^"]+)" class="gallery-card">.*?<img src="([^"]+)"',
        source_content,
        flags=re.DOTALL,
    ):
        href, src = match.groups()
        normalized = normalize_href(href, source_path)
        if normalized:
            source_images[normalized] = src
    return source_images


def english_equivalent_for(target_path: str, target_lang: str) -> str | None:
    for group in collect_page_groups().values():
        if group.get(target_lang) == target_path:
            return group.get("en")
    return None


def translated_equivalent_for(source_path: str, target_lang: str) -> str | None:
    for group in collect_page_groups().values():
        if group.get("en") == source_path:
            return group.get(target_lang)
    return None


def old_index_labels(old_page: OldTravelPage) -> dict[str, str]:
    labels: dict[str, str] = {}
    for section in old_page.sections:
        for item in section.items:
            target = normalize_href(item.href, old_page.path) if item.href else None
            if target and item.label:
                labels[target] = item.label
    return labels


def old_index_section_titles(old_page: OldTravelPage) -> list[str]:
    if not old_page.sections:
        return [old_page.heading]
    titles = [section.title for section in old_page.sections]
    if old_page.heading:
        titles[0] = old_page.heading
    return titles


def old_index_section_title_map(old_page: OldTravelPage) -> dict[str, str]:
    titles = old_index_section_titles(old_page)

    def title_at(index: int, fallback: str) -> str:
        return titles[index] if index < len(titles) else fallback

    return {
        "Highlights": old_page.heading,
        "World": title_at(1, old_page.heading),
        "Architecture and Infrastructure": title_at(2, old_page.heading),
        "Flora": title_at(4, old_page.heading),
        "Water": title_at(5, old_page.heading),
        "Patterns": title_at(7, old_page.heading),
        "Personal": title_at(9, old_page.heading),
    }


def render_index_card(card_html: str, old_page: OldTravelPage, source_path: Path, labels: dict[str, str]) -> str:
    href = extract_attr(card_html, "href")
    source_target = normalize_href(href, source_path) if href else None
    translated_target = translated_equivalent_for(source_target, old_page.lang) if source_target else None
    label = labels.get(translated_target or "")
    if not label:
        title_match = re.search(r'<h3 class="card-title">(.*?)</h3>', card_html, flags=re.DOTALL)
        label = strip_tags(title_match.group(1)) if title_match else ""

    card = card_html
    if translated_target:
        href = os.path.relpath(REPO_ROOT / translated_target, old_page.path.parent).replace(os.sep, "/")
        card = re.sub(r'(<a\b[^>]*\bhref=")[^"]*(")', rf"\g<1>{html.escape(href)}\2", card, count=1)
    if label:
        escaped_label = html.escape(label)
        card = re.sub(r'(<img\b[^>]*\balt=")[^"]*(")', rf"\g<1>{escaped_label}\2", card, count=1)
        card = re.sub(
            r'(<h3 class="card-title">).*?(</h3>)',
            rf"\g<1>{escaped_label}\2",
            card,
            count=1,
            flags=re.DOTALL,
        )
    return re.sub(
        r'\s*<p class="card-description">.*?</p>',
        "",
        card,
        count=1,
        flags=re.DOTALL,
    )


def render_index_main(content: str, old_page: OldTravelPage, source_path: Path) -> str:
    labels = old_index_labels(old_page)
    section_titles = old_index_section_title_map(old_page)

    def render_section(match: re.Match[str]) -> str:
        section = match.group(0)
        heading_match = re.search(r'<div class="section-header">\s*<h2>(.*?)</h2>\s*</div>', section, flags=re.DOTALL)
        source_heading = strip_tags(heading_match.group(1)) if heading_match else ""
        translated_heading = section_titles.get(source_heading)
        if translated_heading:
            section = re.sub(
                r'(<div class="section-header">\s*<h2>).*?(</h2>\s*</div>)',
                rf"\g<1>{html.escape(translated_heading)}\2",
                section,
                count=1,
                flags=re.DOTALL,
            )
        return re.sub(
            r'<a\b[^>]*\bhref="[^"]+"[^>]*class="gallery-card"[^>]*>.*?</a>',
            lambda card_match: render_index_card(card_match.group(0), old_page, source_path, labels),
            section,
            flags=re.DOTALL,
        )

    return re.sub(
        r'<section class="gallery-section">.*?</section>',
        render_section,
        content,
        flags=re.DOTALL,
    )


def rewrite_linked_image_sources(
    translated_content: str,
    source_content: str,
    source_path: Path,
    translated_path: Path,
    target_lang: str,
) -> str:
    source_images = source_index_image_map(source_content, source_path)
    if not source_images:
        return translated_content

    def replace_item(match: re.Match[str]) -> str:
        item_html = match.group(0)
        href_match = re.search(r'<a[^>]*href="([^"]+)"', item_html)
        if not href_match:
            return item_html
        target = normalize_href(href_match.group(1), translated_path)
        if not target:
            return item_html
        english_target = english_equivalent_for(target, target_lang)
        if not english_target:
            return item_html
        source_src = source_images.get(english_target)
        if not source_src:
            return item_html
        return re.sub(
            r'(<img\b[^>]*\bsrc=")[^"]*(")',
            rf"\g<1>{html.escape(source_src)}\2",
            item_html,
            count=1,
        )

    return re.sub(r"<li\b.*?</li>", replace_item, translated_content, flags=re.DOTALL)


def rewrite_content_image_sources(
    translated_content: str,
    source_content: str,
    source_path: Path,
    translated_path: Path,
    target_lang: str,
) -> str:
    translated_content = rewrite_linked_image_sources(
        translated_content,
        source_content,
        source_path,
        translated_path,
        target_lang,
    )
    source_srcs = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', source_content)
    if not source_srcs:
        return translated_content

    index = 0

    def replace_src(match: re.Match[str]) -> str:
        nonlocal index
        if index >= len(source_srcs):
            return match.group(0)
        source_src = html.escape(source_srcs[index])
        index += 1
        return f'{match.group(1)}{source_src}{match.group(2)}'

    return re.sub(r'(<img\b[^>]*\bsrc=")[^"]*(")', replace_src, translated_content)


def render_fallback_content(content: str, old_page: OldTravelPage, source_path: Path) -> str:
    translated_content = old_page.content_html or f"<h2>{html.escape(old_page.heading)}</h2>"
    translated_content = rewrite_content_image_sources(
        translated_content,
        content,
        source_path,
        old_page.path,
        old_page.lang,
    )
    fallback = f'''            <section class="main-content">
                <article class="content-card">
{translated_content}
                </article>
            </section>

            '''
    footer_match = re.search(r"(\s*(?:<!-- Footer.*?-->\s*)?<footer\b)", content, flags=re.DOTALL)
    if not footer_match:
        raise ValueError("Could not find footer for fallback content")
    footer_start = footer_match.start(1)
    hero_match = re.search(r'<section class="[^"]*hero[^"]*"[^>]*>.*?</section>', content, flags=re.DOTALL)
    if hero_match:
        return content[: hero_match.end()] + "\n\n" + fallback + content[footer_start:]
    return content[:footer_start] + fallback + content[footer_start:]


def abstract_page_for_language_pages() -> dict[str, str]:
    """Map each rendered travel page to the Q315 abstract page it comes from.

    The language switcher must link the abstract page as well as the eight
    languages -- ``verify_language_footer`` requires it and ratchets the failure
    count at zero. The mapping lives in the content-migration registry, which is
    the same source the verifier reads, so the two cannot drift apart.
    """
    registry = REPO_ROOT / "src/main/abstract/content-migration-registry.csv"
    if not registry.exists():
        return {}
    mapping: dict[str, str] = {}
    with registry.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            abstract_path = row.get("abstract_path", "")
            if not abstract_path:
                continue
            for language in LANGUAGE_ORDER:
                target = row.get(f"target_{language}", "")
                if target:
                    mapping[target] = abstract_path
    return mapping


ABSTRACT_PAGE_FOR = abstract_page_for_language_pages()


def render_langlist(group: dict[str, str], current_lang: str, current_file: Path, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    lines = [f'                        <ul{class_attr} id="langlist">']
    # The abstract page leads the switcher: it is the source every language page
    # is rendered from, and the footer contract requires a link to it.
    q315_target = group.get("q315") or ABSTRACT_PAGE_FOR.get(repo_rel(current_file), "")
    for lang in ("q315", *LANGUAGE_ORDER):
        target = q315_target if lang == "q315" else group.get(lang)
        if not target:
            continue
        href = os.path.relpath(REPO_ROOT / target, current_file.parent).replace(os.sep, "/")
        highlight = ' class="highlight"' if lang == current_lang else ""
        label = "Q315" if lang == "q315" else LANGUAGE_NAMES[lang]
        span_open = '<span lang="zxx">' if lang == "q315" else f'<span lang="{lang}">'
        lines.extend(
            [
                f'                            <li{highlight} id="{lang}page" rel="hasPart" resource="#{lang}page">',
                f"                                {span_open}",
                f'                                    <a class="langlink" href="{html.escape(href)}" property="url" typeof="WebPage">',
                f'                                        <span property="inLanguage">{label}</span>',
                "                                    </a>",
                "                                </span>",
                "                            </li>",
            ]
        )
    lines.append("                        </ul>")
    return "\n".join(lines)


def replace_langlist(content: str, group: dict[str, str], current_lang: str, current_file: Path) -> str:
    class_name = "lang-list" if is_city_detail_path(current_file) else ""
    rendered = "\n" + render_langlist(group, current_lang, current_file, class_name)
    return replace_one(r'\s*<ul\b([^>]*\s)?id="langlist"[^>]*>.*?</ul>', rendered, content)


def replace_footer_language_block(content: str, group: dict[str, str], current_lang: str, current_file: Path) -> str:
    class_name = "lang-list" if is_city_detail_path(current_file) else ""
    lang_section = f'''                    <!-- Language Section -->
                    <section class="lang-section" id="langsection">
{render_langlist(group, current_lang, current_file, class_name)}
                    </section>'''
    if re.search(r'<section\b[^>]*id="langsection"[^>]*>.*?</section>', content, flags=re.DOTALL):
        return re.sub(
            r'\s*<section\b[^>]*id="langsection"[^>]*>.*?</section>',
            "\n" + lang_section,
            content,
            count=1,
            flags=re.DOTALL,
        )
    # Some pages carry a bare lang-selector with no wrapping langsection. Replace
    # it in place; appending a second switcher beside it breaks the footer
    # contract, which requires exactly one.
    if re.search(r'\s*<div class="lang-selector">.*?</div>', content, flags=re.DOTALL):
        return re.sub(
            r'\s*<div class="lang-selector">.*?</div>',
            "\n" + lang_section,
            content,
            count=1,
            flags=re.DOTALL,
        )
    if re.search(r'\s*<!-- Language Links -->\s*<div class="footer-languages">.*?</div>', content, flags=re.DOTALL):
        return re.sub(
            r'\s*<!-- Language Links -->\s*<div class="footer-languages">.*?</div>',
            "\n" + lang_section,
            content,
            count=1,
            flags=re.DOTALL,
        )
    if '<p class="footer-credits">' in content:
        return content.replace('                <p class="footer-credits">', lang_section + '\n                <p class="footer-credits">', 1)

    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", content, flags=re.DOTALL)
    if not footer_match:
        return content
    footer = footer_match.group(0)
    # A few bespoke pages use an English-only button selector. Keep their
    # styled footer container and localized heading, replacing only the links.
    if re.search(r'<div class="language-selector">.*?</div>', footer, flags=re.DOTALL):
        footer = re.sub(
            r'\s*<div class="language-selector">.*?</div>',
            "\n" + render_langlist(group, current_lang, current_file),
            footer,
            count=1,
            flags=re.DOTALL,
        )
        return content[:footer_match.start()] + footer + content[footer_match.end():]

    footer = footer.replace("</footer>", lang_section + "\n        </footer>", 1)
    return content[:footer_match.start()] + footer + content[footer_match.end():]


def move_langlist_into_footer(content: str) -> str:
    """Move an existing language section into the footer without restyling it."""
    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", content, flags=re.DOTALL)
    if not footer_match or 'id="langlist"' in footer_match.group(0):
        return content

    section_match = re.search(
        r'\s*<section\b[^>]*class="[^"]*language-section[^"]*"[^>]*>.*?'
        r'<ul\b[^>]*id="langlist"[^>]*>.*?</ul>.*?</section>',
        content,
        flags=re.DOTALL,
    )
    if not section_match:
        return content

    section = section_match.group(0).strip()
    without_section = content[:section_match.start()] + content[section_match.end():]
    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", without_section, flags=re.DOTALL)
    if not footer_match:
        return content
    footer = footer_match.group(0).replace("</footer>", f"    {section}\n        </footer>", 1)
    return without_section[:footer_match.start()] + footer + without_section[footer_match.end():]


def repair_orphan_footer(content: str) -> str:
    """Restore a missing opening footer around an existing footer body."""
    if re.search(r"<footer\b", content) or "</footer>" not in content:
        return content
    marker = re.search(
        r'\s*(?:<!-- Language Section -->\s*)?<section\b[^>]*id="langsection"',
        content,
        flags=re.DOTALL,
    )
    if not marker:
        return content
    opening = '\n            <footer>\n                <div class="footer-content">\n'
    return content[:marker.start()] + opening + content[marker.start():]


COUNTRY_LANGLIST_CSS = '''
            #langlist {
                list-style: none;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-wrap: wrap;
                gap: var(--space-lg, 1rem);
                padding: 0;
                margin: 0;
            }

            #langlist li {
                position: relative;
            }

            #langlist a {
                text-decoration: none;
                color: var(--text-muted, inherit);
                font-size: var(--text-sm, 0.95rem);
                letter-spacing: 0.08em;
                padding: var(--space-sm, 0.5rem) var(--space-md, 1rem);
                border-radius: 8px;
                transition: all 0.3s ease;
                display: block;
                background: rgba(212, 165, 116, 0.06);
                border: 1px solid rgba(212, 165, 116, 0.15);
                white-space: nowrap;
            }

            #langlist a:hover {
                background: rgba(212, 165, 116, 0.12);
                border-color: rgba(212, 165, 116, 0.3);
                color: var(--baltic-deep-amber, currentColor);
                transform: translateY(-2px);
                box-shadow: var(--shadow-sm, 0 4px 12px rgba(0, 0, 0, 0.12));
            }

            #langlist .highlight a {
                background: linear-gradient(135deg, var(--baltic-deep-teal, #0f766e), var(--baltic-amber, #d4a574));
                color: var(--baltic-cream, #fffaf0);
                border-color: var(--baltic-deep-amber, #b7791f);
            }
'''


def ensure_country_langlist_css(content: str) -> str:
    if "#langlist {" in content:
        return content
    if ".lang-list {" in content:
        return content
    if "            .licence {" in content:
        return content.replace("            .licence {", COUNTRY_LANGLIST_CSS + "\n            .licence {", 1)
    return content.replace("        </style>", COUNTRY_LANGLIST_CSS + "\n        </style>", 1)


def update_common_language_bits(content: str, lang: str) -> str:
    content = replace_one(r'<html lang="[^"]+">', f'<html lang="{lang}">', content)
    content = re.sub(
        r'<meta ([^>]*http-equiv="Content-Language"[^>]*)content="[^"]*"([^>]*)/>',
        rf'<meta \1content="{lang}"\2/>',
        content,
        count=1,
    )
    content = re.sub(
        r'<meta ([^>]*content=")[^"]*("[^>]*http-equiv="Content-Language"[^>]*)/>',
        rf'<meta \1{lang}\2/>',
        content,
        count=1,
    )
    return content


def localize_country_page(
    source_html: str,
    english_name: str,
    lang: str,
    target_path: Path,
    group: dict[str, str],
) -> str:
    labels = COUNTRY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_name][lang] if lang != "en" else english_name
    content = update_common_language_bits(source_html, lang)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(country)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<p class="site-tagline">).*?(</p>)',
        rf"\g<1>{labels['site_tagline']}\2",
        content,
    )
    home_href = os.path.relpath(REPO_ROOT / lang / "index.html", target_path.parent).replace(os.sep, "/")
    travel_href = os.path.relpath(REPO_ROOT / TRAVEL_INDEX_DIRS[lang] / "index.html", target_path.parent).replace(os.sep, "/")
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Home(</span>)',
        rf"\g<1>{html.escape(home_href)}\2{html.escape(labels['home'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Travel(</span>)',
        rf"\g<1>{html.escape(travel_href)}\2{html.escape(labels['travel'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(country.upper())}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{labels['hero_subtitle']}\2",
        content,
    )
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(country=country))}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\g<1>{labels['credits']}\2",
        content,
    )

    def rewrite_city_href(match: re.Match[str]) -> str:
        href = html.unescape(match.group(1))
        english_target = (REPO_ROOT / "en/photography/countries" / href).resolve()
        rel = os.path.relpath(english_target, target_path.parent).replace(os.sep, "/")
        return f'{match.group(1)[:0]}href="{html.escape(rel)}"'

    content = re.sub(r'href="(\.\./cities/[^"]+)"', rewrite_city_href, content)
    content = translate_image_descriptions(content, lang)
    content = replace_footer_language_block(content, group, lang, target_path)
    content = ensure_country_langlist_css(content)
    return content


def generate_missing_country_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for english_name in COUNTRY_NAME_TRANSLATIONS:
        source_path = REPO_ROOT / country_page_path(english_name, "en")
        if not source_path.exists():
            continue
        source_html = read_text(source_path)
        group = {
            lang: country_page_path(english_name, lang)
            for lang in LANGUAGE_ORDER
            if (lang == "en" or lang in COUNTRY_NAME_TRANSLATIONS[english_name])
        }
        groups[group["en"]] = group
        for lang in LANGUAGE_ORDER:
            if lang in ("en", "fr"):
                continue
            target = group[lang]
            target_path = REPO_ROOT / target
            if target_path.exists():
                continue
            localized = localize_country_page(source_html, english_name, lang, target_path, group)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(target_path, localized, dry_run)
            changed.append(target_path)
    return changed


def localize_city_page(
    source_html: str,
    english_country: str,
    city_name: str,
    lang: str,
    target_path: Path,
    group: dict[str, str],
) -> str:
    labels = CITY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_country][lang] if lang != "en" else english_country
    localized_city = translated_city_name(city_name, lang)
    content = update_common_language_bits(source_html, lang)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(localized_city)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<p class="site-tagline">).*?(</p>)',
        rf"\g<1>{labels['site_tagline']}\2",
        content,
    )
    home_href = os.path.relpath(REPO_ROOT / lang / "index.html", target_path.parent).replace(os.sep, "/")
    travel_href = os.path.relpath(REPO_ROOT / TRAVEL_INDEX_DIRS[lang] / "index.html", target_path.parent).replace(os.sep, "/")
    country_href = os.path.relpath(REPO_ROOT / country_page_path(english_country, lang), target_path.parent).replace(os.sep, "/")
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Home(</span>)',
        rf"\g<1>{html.escape(home_href)}\2{html.escape(labels['home'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Travel(</span>)',
        rf"\g<1>{html.escape(travel_href)}\2{html.escape(labels['travel'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*countries/[^"]*("[^>]*>\s*<span property="name">)[^<]*(</span>)',
        rf"\g<1>{html.escape(country_href)}\2{html.escape(country)}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{html.escape(localized_city)}, {html.escape(country)}</p>",
        content,
    )
    content = replace_one(
        r'(<h3 class="region-title">).*?(</h3>)',
        rf"\g<1>{html.escape(country)}\2",
        content,
    )
    content = replace_one(
        r'(<h4 class="city-name">).*?(</h4>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = content.replace(f'href="{html.escape(Path(group["en"]).name)}"', f'href="{html.escape(target_path.name)}"')
    content = rewrite_local_city_hrefs(content, lang)
    content = translate_image_descriptions(content, lang)
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(city=localized_city, country=country))}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\g<1>{labels['credits']}\2",
        content,
    )
    content = replace_footer_language_block(content, group, lang, target_path)
    return content


def city_display_name(city_name: str, lang: str, group: dict[str, str]) -> str:
    if lang == "fr" and group.get("fr"):
        return Path(group["fr"]).stem
    return translated_city_name(city_name, lang)


def update_city_detail_names(
    content: str,
    english_country: str,
    city_name: str,
    lang: str,
    group: dict[str, str],
) -> str:
    labels = CITY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_country][lang] if lang != "en" else english_country
    localized_city = city_display_name(city_name, lang, group)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(localized_city)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{html.escape(localized_city)}, {html.escape(country)}</p>",
        content,
    )
    content = replace_one(
        r'(<h3 class="region-title">).*?(</h3>)',
        rf"\g<1>{html.escape(country)}\2",
        content,
    )
    content = replace_one(
        r'(<h4 class="city-name">).*?(</h4>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    return replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(city=localized_city, country=country))}\2",
        content,
    )


def generate_missing_city_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in expected_city_translation_groups():
        source = group.get("en")
        if not source:
            continue
        source_path = REPO_ROOT / source
        if not source_path.exists():
            continue
        english_country = source_path.parent.name
        city_name = source_path.stem
        source_html = read_text(source_path)
        groups[source] = group
        for lang in LANGUAGE_ORDER:
            if lang in ("en", "fr"):
                continue
            target = group[lang]
            target_path = REPO_ROOT / target
            if target_path.exists():
                continue
            localized = localize_city_page(source_html, english_country, city_name, lang, target_path, group)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(target_path, localized, dry_run)
            changed.append(target_path)
    return changed


def update_indic_page(source_html: str, old_page: OldTravelPage, group: dict[str, str], source_path: Path) -> str:
    content = update_common_language_bits(source_html, old_page.lang)
    content = replace_one(r"<title>.*?</title>", f"<title>{html.escape(old_page.title)}</title>", content)
    content = replace_one(
        r'<p class="site-tagline">.*?</p>',
        f'<p class="site-tagline">{COUNTRY_PAGE_LABELS[old_page.lang]["site_tagline"]}</p>',
        content,
    )
    nav_values = list(old_page.nav_labels.values())
    home_label = nav_values[0][1] if nav_values else LANGUAGE_NAMES[old_page.lang]
    research = nav_values[1] if len(nav_values) > 1 else ("../research/research.html", "Research")
    writings = nav_values[3] if len(nav_values) > 3 else ("../writings/index.html", "Writings")
    travel_label = nav_values[-1][1] if nav_values else old_page.heading
    travel_dir = TRAVEL_INDEX_DIRS[old_page.lang].parts[1]
    content = replace_one(r'(<span property="name">)Home(</span>)', rf"\1{home_label}\2", content)
    content = replace_one(r'(<span property="name">)Research(</span>)', rf"\1{research[1]}\2", content)
    content = replace_one(r'(<span property="name">)Writings(</span>)', rf"\1{writings[1]}\2", content)
    content = replace_one(r'(<span property="name">)Travel(</span>)', rf"\1{travel_label}\2", content)
    content = content.replace('../research/research.html', research[0])
    content = content.replace('../writings/index.html', writings[0])
    content = content.replace('../travel/index.html', f'../{travel_dir}/index.html')
    content = re.sub(
        r'<h([12]) class="hero-title">.*?</h\1>',
        lambda m: f'<h{m.group(1)} class="hero-title">{html.escape(old_page.heading)}</h{m.group(1)}>',
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(r'\s*<p class="hero-subtitle">.*?</p>', "", content)
    content = replace_one(r'\s*<p class="hero-description">.*?</p>', "", content)
    if repo_rel(source_path) == "en/travel/index.html":
        content = render_index_main(content, old_page, source_path)
    elif old_page.sections:
        try:
            content = render_gallery(content, old_page)
        except ValueError:
            content = render_fallback_content(content, old_page, source_path)
    else:
        content = render_fallback_content(content, old_page, source_path)
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\1{COUNTRY_PAGE_LABELS[old_page.lang]['language_switcher']}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\1{COUNTRY_PAGE_LABELS[old_page.lang]['site_tagline']}\2",
        content,
    )
    return replace_langlist(content, group, old_page.lang, old_page.path)


def refresh_indic_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in groups.values():
        source = group.get("en")
        if not source:
            continue
        source_path = REPO_ROOT / source
        if not source_path.exists():
            continue
        source_html = read_text(source_path)
        for lang in INDIC_LANGS:
            target = group.get(lang)
            if not target:
                continue
            target_path = REPO_ROOT / target
            if not target_path.exists():
                continue
            current_html = read_text(target_path)
            if "#sidebar" not in current_html:
                continue
            old_page = parse_old_page(target_path, lang)
            refreshed = update_indic_page(source_html, old_page, group, source_path)
            if refreshed != current_html:
                write_text(target_path, refreshed, dry_run)
                changed.append(target_path)
    return changed


def refresh_language_selectors(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in groups.values():
        for lang in REFRESH_SELECTOR_LANGS:
            target = group.get(lang)
            if not target:
                continue
            path = REPO_ROOT / target
            if not path.exists():
                continue
            content = read_text(path)
            updated = update_common_language_bits(content, lang)
            updated = repair_orphan_footer(updated)
            if is_country_detail_path(path) or is_city_detail_path(path):
                updated = translate_image_descriptions(updated, lang)
            if is_country_detail_path(path):
                updated = ensure_country_langlist_css(updated)
            if is_city_detail_path(path):
                source = group.get("en")
                if source:
                    source_path = Path(source)
                    updated = update_city_detail_names(updated, source_path.parent.name, source_path.stem, lang, group)
                updated = rewrite_local_city_hrefs(updated, lang)
            if 'id="langlist"' in updated:
                updated = replace_langlist(updated, group, lang, path)
                updated = move_langlist_into_footer(updated)
            else:
                updated = replace_footer_language_block(updated, group, lang, path)
            updated = ensure_country_langlist_css(updated)
            if updated != content:
                write_text(path, updated, dry_run)
                changed.append(path)
    return changed


def missing_static_translations(groups: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for group in expected_translation_groups():
        source = group.get("en")
        if not source:
            continue
        absent = [lang for lang in LANGUAGE_ORDER if lang not in group or not (REPO_ROOT / group[lang]).exists()]
        if absent:
            missing[source] = absent
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    parser.add_argument(
        "--links-only",
        action="store_true",
        help="Only rebuild travel language selectors and lang metadata",
    )
    parser.add_argument(
        "--skip-country-generation",
        action="store_true",
        help="Do not generate missing translated country detail pages",
    )
    parser.add_argument(
        "--skip-city-generation",
        action="store_true",
        help="Do not generate missing translated city detail pages",
    )
    parser.add_argument(
        "--missing-report",
        action="store_true",
        help="Report missing translated pages from the shared travel mapping",
    )
    args = parser.parse_args()

    groups = collect_page_groups()
    if not groups:
        raise SystemExit("No travel page language groups found")

    changed: list[Path] = []
    if not args.links_only and not args.skip_country_generation:
        changed.extend(generate_missing_country_pages(groups, args.dry_run))
    if not args.links_only and not args.skip_city_generation:
        changed.extend(generate_missing_city_pages(groups, args.dry_run))

    changed.extend(refresh_language_selectors(groups, args.dry_run))
    if not args.links_only:
        changed.extend(refresh_indic_pages(groups, args.dry_run))

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {len(set(changed))} travel pages")
    for path in sorted(set(changed)):
        print(f"  {repo_rel(path)}")
    if args.missing_report:
        missing = missing_static_translations(groups)
        if missing:
            print("\nMissing translated equivalents:")
            for source, langs in sorted(missing.items()):
                print(f"  {source}: {', '.join(langs)}")
        else:
            print("\nNo missing translated equivalents found in the shared travel mapping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
