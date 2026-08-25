#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""CSV-driven append/update tool for curated list pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from bs4.element import Tag

from file_rewrite import rewrite_text_file
from paths import REPO_ROOT, to_repo_relative
from wikibase_api import DEFAULT_API, WikibaseClient, WikibaseError
from wikibase_write import datavalue, load_env

from languages import ORDER as LANGUAGES
WIKIDATA_RE = re.compile(
    r"^https?://www\.wikidata\.org/(?:wiki|entity)/Q[1-9][0-9]*$"
)
TYPE_ALIASES = {
    "film": "Movie",
    "movie": "Movie",
    "series": "TVSeries",
    "tvseries": "TVSeries",
    "tv-series": "TVSeries",
    "podcast": "PodcastSeries",
    "podcast-series": "PodcastSeries",
    "book": "Book",
    "museum": "Museum",
    "gallery": "ArtGallery",
    "artgallery": "ArtGallery",
    "art-gallery": "ArtGallery",
    "person": "Person",
    "artist": "Person",
    "singer": "Person",
    "musicgroup": "MusicGroup",
    "music-group": "MusicGroup",
    "band": "MusicGroup",
    "quote": "Quote",
    "cv": "CVEntry",
    "cv-entry": "CVEntry",
    "cventry": "CVEntry",
    "publication": "CVEntry",
    "conference": "CVEntry",
    "journal": "CVEntry",
}
# Items that cannot be bound on their Q315 source yet. Binding one makes the
# round-trip verifier require its stored label to appear on every language page,
# so an item whose Wikibase value disagrees with the published pages must be
# corrected in Wikibase first.
#
# Binding is all-or-nothing per container: render_page.py places labels by slot
# *position*, so a container holding one unbound entry among bound ones renders
# the bound labels into shifted positions and leaves the unbound slot showing
# stale text -- dropping one name from the page and duplicating another. A
# container with any QID listed here is therefore left entirely unbound until it
# can be bound completely. See museum_entries_are_bindable().
UNBOUND_CONTENT_QIDS: frozenset[str] = frozenset()
ABSTRACT_CONTENT_ITEM = "Q3185"
INSTANCE_OF_PROPERTY = "P8"
WIKIDATA_ITEM_PROPERTY = "P4"
MONOLINGUAL_CONTENT_PROPERTY = "P40"
CONTENT_RENDER_FUNCTION = "Q4182"
TRAILING_URL_RE = re.compile(r"(?:,\s*|\s+)(https?://[^\s<]+)\s*$")
LINK_TEXT = {
    "en": "Link",
    "fr": "Lien",
    "ml": "ലിങ്ക്",
    "pa": "ਲਿੰਕ",
    "hi": "लिंक",
    "pt": "Link",
    "es": "Enlace",
    "it": "Collegamento",
}
CV_SIMPLE_PATHS = {
    "en": "en/research/index.html",
    "fr": "fr/recherche/index.html",
    "ml": "ml/ഗവേഷണം/index.html",
    "pa": "pa/ਖੋਜ/index.html",
    "hi": "hi/अनुसंधान/index.html",
    "pt": "pt/pesquisa/index.html",
    "es": "es/investigación/index.html",
    "it": "it/ricerca/index.html",
}


@dataclass(frozen=True)
class ColumnSpec:
    """One CSV column, and what makes a row valid for it.

    The families used to declare their columns twice -- once as a branch in
    ``default_fieldnames`` and again as a branch in ``validate_rows`` -- so a new
    column had to be added in two places and the README described a third
    version. Both now read this list.
    """

    name: str
    #: The row is invalid without a value here (or in one of `alternatives`).
    required: bool = False
    #: A `<name>_<language>` column satisfies the requirement too, which is how
    #: the legacy `name_en` columns still work.
    per_language: bool = False
    #: Sibling columns that satisfy the requirement instead, such as `year_qid`
    #: standing in for `year`.
    alternatives: tuple[str, ...] = ()

    def satisfied_by(self, row: "ContentRow") -> bool:
        for column in (self.name, *self.alternatives):
            if row.data.get(column, "").strip():
                return True
            if self.per_language and any(
                row.data.get(f"{column}_{language}", "").strip() for language in LANGUAGES
            ):
                return True
        return False


ID_COLUMNS = (ColumnSpec("id"), ColumnSpec("type"))
NAMED_ENTRY = (ColumnSpec("name", required=True, per_language=True),)
WIKIDATA_COLUMNS = (ColumnSpec("wikidata_url"), ColumnSpec("local_qid"))

@dataclass(frozen=True)
class PageTarget:
    language: str
    path: Path


@dataclass(frozen=True)
class FamilyConfig:
    name: str
    csv_name: str
    renderer: str
    paths: dict[str, str]
    allowed_types: tuple[str, ...]
    wikidata_required: bool
    sort_entries: bool = True
    q315_path: str = ""
    # True when the CSV holds every entry on the Q315 source, so a binding on the
    # page with no CSV row is a real orphan. cv.csv only appends, so its source
    # legitimately carries entries the CSV never mentions.
    mirrors_q315: bool = True

    def targets(self) -> list[PageTarget]:
        return [
            PageTarget(language=language, path=REPO_ROOT / relative_path)
            for language, relative_path in self.paths.items()
        ]

    @property
    def q315_target(self) -> Path | None:
        return REPO_ROOT / self.q315_path if self.q315_path else None


FAMILIES: dict[str, FamilyConfig] = {
    "books": FamilyConfig(
        name="books",
        csv_name="books.csv",
        renderer="ordered-list",
        allowed_types=("Book",),
        wikidata_required=False,
        q315_path="Q315/Q3638/Q3640.html",
        paths={
            "en": "en/writings/books-i-read.html",
            "fr": "fr/ecrits/livres-lus.html",
            "ml": "ml/രചനകൾ/വായിച്ച-പുസ്തകങ്ങൾ.html",
            "pa": "pa/ਲਿਖਤਾਂ/ਪੜ੍ਹੀਆਂ  ਕਿਤਾਬਾਂ.html",
            "hi": "hi/रचनायें/पढ़ी हुई पुस्तकें.html",
            "pt": "pt/escritos/livros-lidos.html",
            "es": "es/escritos/libros-leídos.html",
            "it": "it/scritti/libri-letti.html",
        },
    ),
    "films": FamilyConfig(
        name="films",
        csv_name="films-series-documentaries.csv",
        renderer="ordered-list",
        allowed_types=("Movie", "TVSeries", "PodcastSeries"),
        wikidata_required=True,
        q315_path="Q315/Q3638/Q3641.html",
        paths={
            "en": "en/writings/films-series-documentaries.html",
            "fr": "fr/ecrits/films-séries-documentaires.html",
            "ml": "ml/രചനകൾ/സിനിമകൾ-പരമ്പരകൾ-ഡോക്യുമെന്ററികൾ.html",
            "pa": "pa/ਲਿਖਤਾਂ/ਫਿਲਮਾਂ-ਲੜੀਵਾਰ-ਦਸਤਾਵੇਜ਼ੀ ਫਿਲਮਾਂ.html",
            "hi": "hi/रचनायें/फिल्म-श्रृंखला-वृत्तचित्र.html",
            "pt": "pt/escritos/filmes-séries-documentários.html",
            "es": "es/escritos/películas-series-documentales.html",
            "it": "it/scritti/film-serie-documentari.html",
        },
    ),
    "museums": FamilyConfig(
        name="museums",
        csv_name="museums-galleries.csv",
        renderer="museum-grid",
        allowed_types=("Museum", "ArtGallery"),
        wikidata_required=True,
        q315_path="Q315/Q3638/Q3643.html",
        paths={
            "en": "en/writings/museums-galleries.html",
            "fr": "fr/ecrits/musées-galeries.html",
            "ml": "ml/രചനകൾ/മ്യൂസിയങ്ങൾ-ഗാലറികൾ.html",
            "pa": "pa/ਲਿਖਤਾਂ/ਅਜਾਇਬ-ਘਰ-ਗੈਲਰੀਆਂ.html",
            "hi": "hi/रचनायें/संग्रहालय-दीर्घाएँ.html",
            "pt": "pt/escritos/museus-galerias.html",
            "es": "es/escritos/museos-galerías.html",
            "it": "it/scritti/musei-gallerie.html",
        },
    ),
    "music": FamilyConfig(
        name="music",
        csv_name="music.csv",
        renderer="ordered-list",
        allowed_types=("Person", "MusicGroup"),
        wikidata_required=True,
        q315_path="Q315/Q3638/Q3642.html",
        paths={
            "en": "en/writings/music.html",
            "fr": "fr/ecrits/musique.html",
            "ml": "ml/രചനകൾ/സംഗീതം.html",
            "pa": "pa/ਲਿਖਤਾਂ/ਸੰਗੀਤ.html",
            "hi": "hi/रचनायें/संगीत.html",
            "pt": "pt/escritos/música.html",
            "es": "es/escritos/música.html",
            "it": "it/scritti/musica.html",
        },
    ),
    "quotes": FamilyConfig(
        name="quotes",
        csv_name="quotes.csv",
        renderer="quote-grid",
        allowed_types=("Quote",),
        wikidata_required=False,
        sort_entries=False,
        q315_path="Q315/Q3638/Q3639.html",
        paths={
            "en": "en/writings/quotes.html",
            "fr": "fr/ecrits/citations.html",
            "ml": "ml/രചനകൾ/ഉദ്ധരണികൾ.html",
            "pa": "pa/ਲਿਖਤਾਂ/ਹਵਾਲੇ.html",
            "hi": "hi/रचनायें/उद्धरण.html",
            "pt": "pt/escritos/citações.html",
            "es": "es/escritos/citas.html",
            "it": "it/scritti/citazioni.html",
        },
    ),
    "cv": FamilyConfig(
        name="cv",
        csv_name="cv.csv",
        renderer="detailed-cv",
        allowed_types=("CVEntry",),
        wikidata_required=False,
        sort_entries=False,
        mirrors_q315=False,
        q315_path="Q315/Q3636/Q3646.html",
        paths={
            "en": "en/research/cv-detailed.html",
            "fr": "fr/recherche/cv-détaillé.html",
            "ml": "ml/ഗവേഷണം/വിശദമായ-സിവി.html",
            "pa": "pa/ਖੋਜ/ਵਿਸਤ੍ਰਿਤ-ਸੀਵੀ.html",
            "hi": "hi/अनुसंधान/विस्तृत-सीवी.html",
            "pt": "pt/pesquisa/cv-detalhado.html",
            "es": "es/investigación/cv-detallado.html",
            "it": "it/ricerca/cv-dettagliato.html",
        },
    ),
}


FAMILY_COLUMNS: dict[str, tuple[ColumnSpec, ...]] = {
    "books": (
        *ID_COLUMNS,
        *NAMED_ENTRY,
        ColumnSpec("creator"),
        ColumnSpec("creator_qid"),
        *WIKIDATA_COLUMNS,
    ),
    "films": (*ID_COLUMNS, *NAMED_ENTRY, *WIKIDATA_COLUMNS),
    "music": (*ID_COLUMNS, *NAMED_ENTRY, *WIKIDATA_COLUMNS),
    "museums": (*ID_COLUMNS, *NAMED_ENTRY, ColumnSpec("type_label"), *WIKIDATA_COLUMNS),
    "quotes": (
        *ID_COLUMNS,
        ColumnSpec("category", required=True, per_language=True),
        ColumnSpec("quote", required=True, per_language=True),
        ColumnSpec("attribution", required=True, per_language=True),
        ColumnSpec("local_qid"),
    ),
    "cv": (
        *ID_COLUMNS,
        ColumnSpec("target"),
        ColumnSpec("section", required=True),
        ColumnSpec("year", required=True, alternatives=("year_qid",)),
        ColumnSpec("year_qid"),
        ColumnSpec("content", required=True, per_language=True),
        ColumnSpec("simple_content"),
        ColumnSpec("part_qids"),
        ColumnSpec("wikidata_url"),
        ColumnSpec("local_qid"),
        ColumnSpec("simple_local_qid"),
    ),
}


class ContentUpdateError(Exception):
    """Raised when input data or target pages cannot be updated safely."""


@dataclass(frozen=True)
class ContentRow:
    family: str
    row_number: int
    data: dict[str, str]

    @property
    def stable_id(self) -> str:
        row_id = self.data.get("id", "").strip()
        if row_id:
            return row_id
        qid = wikidata_qid(self.wikidata_url)
        if qid:
            return qid
        if self.family == "quotes":
            return slugify(self.data.get("quote", "") or self.data.get("quote_en", ""))
        if self.family == "cv":
            key = "|".join(
                (
                    self.data.get("section", ""),
                    self.data.get("year_qid", "") or self.data.get("year", ""),
                    self.data.get("content", "") or self.data.get("content_en", ""),
                )
            )
            return f"cv-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}" if key else ""
        return slugify(self.data.get("name", "") or self.data.get("name_en", ""))

    @property
    def item_type(self) -> str:
        raw_type = self.data.get("type", "").strip()
        return TYPE_ALIASES.get(raw_type.casefold(), raw_type)

    @property
    def wikidata_url(self) -> str:
        return self.data.get("wikidata_url", "").strip()

    @property
    def local_qid(self) -> str:
        return self.data.get("local_qid", "").strip()

    def localized(self, field: str, language: str, *, required: bool = True) -> str:
        value = self.data.get(field, "").strip()
        if not value:
            value = self.data.get(f"{field}_{language}", "").strip()
        if not value:
            value = self.data.get(f"{field}_en", "").strip()
        if required and not value:
            raise ContentUpdateError(
                f"{self.family}:{self.row_number}: missing {field}"
            )
        return value


@dataclass
class PageChange:
    family: str
    path: Path
    language: str
    added: int
    skipped: int
    repaired: int
    changed: bool


@dataclass(frozen=True)
class ExtractedRow:
    item_type: str
    name: str
    wikidata_url: str
    local_qid: str = ""
    creator: str = ""
    creator_qid: str = ""
    type_label: str = ""


def read_rows(family: FamilyConfig, csv_path: Path) -> list[ContentRow]:
    return read_rows_with_header(family, csv_path)[1]


def write_rows(csv_path: Path, fieldnames: list[str], rows: list[ContentRow]) -> None:
    output_fields = list(fieldnames)
    if "local_qid" not in output_fields:
        output_fields.append("local_qid")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=output_fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.data)


def read_rows_with_header(family: FamilyConfig, csv_path: Path) -> tuple[list[str], list[ContentRow]]:
    if not csv_path.exists():
        raise ContentUpdateError(f"CSV file not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ContentUpdateError(f"{csv_path}: missing CSV header")
        rows = []
        for index, row in enumerate(reader, start=2):
            if row.get(None):
                raise ContentUpdateError(
                    f"{csv_path}: line {index}: too many CSV fields"
                )
            if any(value.strip() for value in row.values() if value):
                rows.append(
                    ContentRow(family=family.name, row_number=index, data=_clean_row(row))
                )
    validate_rows(family, rows, csv_path)
    return list(reader.fieldnames), rows


def merge_extracted_rows(
    family: FamilyConfig,
    csv_path: Path,
) -> tuple[int, int]:
    if csv_path.exists():
        fieldnames, rows = read_rows_with_header(family, csv_path)
    else:
        fieldnames = default_fieldnames(family)
        rows = []
    extracted = extract_existing_rows(family)
    row_keys = {row_key(row) for row in rows}
    added = 0
    for item in extracted:
        key = extracted_key(item)
        if key in row_keys:
            continue
        data = {
            "id": "",
            "type": item.item_type,
            "name": item.name,
            "wikidata_url": canonical_wikidata_url(item.wikidata_url),
            "local_qid": item.local_qid,
        }
        if family.name == "quotes":
            data = {
                "id": "",
                "type": "Quote",
                "category": item.type_label,
                "quote": item.name,
                "attribution": item.creator,
                "local_qid": item.local_qid,
            }
        if family.name == "books":
            data["creator"] = item.creator
            data["creator_qid"] = item.creator_qid
        if family.name == "museums":
            data["type_label"] = item.type_label
        rows.append(ContentRow(family=family.name, row_number=len(rows) + 2, data=data))
        row_keys.add(key)
        added += 1
    backfilled = backfill_q315_qids(family, rows)
    if backfilled and "creator_qid" not in fieldnames:
        fieldnames = default_fieldnames(family)
    write_rows(csv_path, fieldnames, rows)
    return len(extracted), added, backfilled


def default_fieldnames(family: FamilyConfig) -> list[str]:
    return [column.name for column in FAMILY_COLUMNS[family.name]]


def row_key(row: ContentRow) -> tuple[str, str]:
    if row.family == "cv":
        return ("cv", normalize_text(f"{row.data.get('section', '')}|{row.data.get('year_qid', '') or row.data.get('year', '')}|{cv_content(row, 'en')}"))
    wikidata = wikidata_qid(row.wikidata_url)
    if wikidata:
        return ("wikidata", wikidata)
    return ("name", normalize_text(row.localized("name", "en", required=False)))


def extracted_key(row: ExtractedRow) -> tuple[str, str]:
    wikidata = wikidata_qid(row.wikidata_url)
    if wikidata:
        return ("wikidata", wikidata)
    return ("name", normalize_text(row.name))


def extract_existing_rows(family: FamilyConfig) -> list[ExtractedRow]:
    english_path = family.targets()[0].path
    html_content = english_path.read_text(encoding="utf-8")
    if family.renderer == "ordered-list":
        return extract_ordered_list_rows(html_content, family)
    if family.renderer == "museum-grid":
        return extract_museum_rows(html_content)
    if family.renderer == "quote-grid":
        return extract_quote_rows(html_content)
    raise ContentUpdateError(f"Unsupported renderer: {family.renderer}")


def extract_ordered_list_rows(html_content: str, family: FamilyConfig) -> list[ExtractedRow]:
    soup = BeautifulSoup(html_content, features="html.parser")
    ordered_list = soup.find("ol", class_=re.compile(r"(book-list|media-list|music-list)"))
    if not isinstance(ordered_list, Tag):
        raise ContentUpdateError(f"{family.name}: ordered list target not found")
    rows: list[ExtractedRow] = []
    for item in ordered_list.find_all("li", recursive=False):
        name_node = item.find(attrs={"property": "name"})
        type_node = item.find(attrs={"typeof": True})
        if not name_node or not type_node:
            continue
        wikidata = ""
        same_as = item.find("link", attrs={"property": "sameAs"})
        if same_as and same_as.get("href"):
            wikidata = same_as["href"].strip()
        local_qid = local_qid_from_tag(item)
        creator = ""
        creator_qid = ""
        creator_node = item.find("span", class_="book-author")
        if creator_node:
            creator = creator_node.get_text(" ", strip=True)
            creator_qid = content_qid_from_tag(creator_node)
        rows.append(
            ExtractedRow(
                item_type=str(type_node.get("typeof", "")).strip(),
                name=name_node.get_text(" ", strip=True),
                wikidata_url=wikidata,
                local_qid=local_qid,
                creator=creator,
                creator_qid=creator_qid,
            )
        )
    return rows


def extract_museum_rows(html_content: str) -> list[ExtractedRow]:
    soup = BeautifulSoup(html_content, features="html.parser")
    grid = soup.find("div", class_="museums-grid")
    container = grid if isinstance(grid, Tag) else soup.find("ol")
    if not isinstance(container, Tag):
        raise ContentUpdateError("museums: target not found")
    rows: list[ExtractedRow] = []
    for item in container.find_all(["article", "li"], recursive=False):
        name_node = item.find(attrs={"property": "name"})
        type_node = item.find(attrs={"typeof": re.compile(r"^(Museum|ArtGallery)$")})
        if not name_node or not type_node:
            continue
        same_as = item.find("link", attrs={"property": "sameAs"})
        type_label = item.find("span", class_="museum-type")
        rows.append(
            ExtractedRow(
                item_type=str(type_node.get("typeof", "")).strip(),
                name=name_node.get_text(" ", strip=True),
                wikidata_url=same_as["href"].strip() if same_as and same_as.get("href") else "",
                local_qid=local_qid_from_tag(item),
                type_label=type_label.get_text(" ", strip=True) if type_label else "",
            )
        )
    return rows


def extract_quote_rows(html_content: str) -> list[ExtractedRow]:
    soup = BeautifulSoup(html_content, features="html.parser")
    rows: list[ExtractedRow] = []
    for section in soup.find_all("section", class_="quote-section"):
        heading = section.find(["h2", "h3"], class_=re.compile(r"section-title"))
        category = heading.get_text(" ", strip=True) if heading else ""
        for card in section.find_all("div", class_="quote-card"):
            quote = card.find("p", class_="quote-text")
            attribution = card.find("p", class_="quote-author")
            if not quote or not attribution:
                continue
            rows.append(
                ExtractedRow(
                    item_type="Quote",
                    name=quote.get_text(" ", strip=True),
                    wikidata_url="",
                    local_qid=local_qid_from_tag(card),
                    creator=attribution.get_text(" ", strip=True),
                    type_label=category,
                )
            )
    return rows


def local_qid_from_tag(tag: Tag) -> str:
    source = tag.get("data-q315-source", "")
    match = re.fullmatch(r"local:(Q[1-9][0-9]*)", source)
    return match.group(1) if match else ""


def content_qid_from_tag(tag: Tag) -> str:
    """Read the ``data-content="local:Q…"`` binding an abstract page carries."""
    for attribute in ("data-content", "data-entity"):
        match = re.fullmatch(r"local:(Q[1-9][0-9]*)", str(tag.get(attribute, "")))
        if match:
            return match.group(1)
    return ""


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    cleaned = {key: (value or "").strip() for key, value in row.items() if key}
    if "wikidata_url" in cleaned:
        cleaned["wikidata_url"] = canonical_wikidata_url(cleaned["wikidata_url"])
    return cleaned


def validate_rows(family: FamilyConfig, rows: list[ContentRow], csv_path: Path) -> None:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_wikidata: set[str] = set()

    for row in rows:
        row_id = row.stable_id
        if not row_id:
            errors.append(f"line {row.row_number}: cannot generate id from this row")
        elif row_id in seen_ids:
            errors.append(f"line {row.row_number}: duplicate id {row_id}")
        if row_id:
            seen_ids.add(row_id)

        if row.item_type not in family.allowed_types:
            allowed = ", ".join(family.allowed_types)
            errors.append(f"line {row.row_number}: type must be one of {allowed}")

        for column in FAMILY_COLUMNS[family.name]:
            if column.required and not column.satisfied_by(row):
                names = [column.name, *column.alternatives]
                if column.per_language:
                    names.append(f"{column.name}_<language>")
                wanted = " or ".join(names)
                errors.append(f"line {row.row_number}: missing {wanted}")

        if family.name == "cv":
            try:
                cv_targets(row)
            except ContentUpdateError as error:
                errors.append(str(error).replace(f"cv:{row.row_number}: ", f"line {row.row_number}: "))

        wikidata_url = row.wikidata_url
        if family.wikidata_required and not wikidata_url:
            errors.append(f"line {row.row_number}: wikidata_url is required for {family.name}")
        if wikidata_url and not WIKIDATA_RE.match(wikidata_url):
            errors.append(f"line {row.row_number}: invalid Wikidata URL {wikidata_url}")
        if wikidata_url:
            if wikidata_url in seen_wikidata:
                errors.append(f"line {row.row_number}: duplicate wikidata_url {wikidata_url}")
            seen_wikidata.add(wikidata_url)

    if family.name == "cv":
        for target in family.targets():
            if not target.path.exists():
                errors.append(f"missing target page: {to_repo_relative(target.path)}")
        for relative_path in CV_SIMPLE_PATHS.values():
            path = REPO_ROOT / relative_path
            if not path.exists():
                errors.append(f"missing target page: {to_repo_relative(path)}")
    else:
        for target in family.targets():
            if not target.path.exists():
                errors.append(f"missing target page: {to_repo_relative(target.path)}")

    if errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise ContentUpdateError(f"{csv_path} failed validation:\n{details}")


def render_family(family: FamilyConfig, rows: list[ContentRow], *, apply: bool) -> list[PageChange]:
    if apply and family.q315_path:
        raise ContentUpdateError(
            f"{family.name}: rendered language pages are generated from {family.q315_path}; "
            "writing them directly would bypass Q315 and can duplicate entries whose "
            "markup the renderer has already rewritten. Use --mode q315-apply, then "
            "src/main/abstract/render_page.py. --mode preview remains available as a "
            "read-only diagnostic."
        )
    if family.name == "cv":
        return render_cv_family(rows, apply=apply)
    changes = []
    for target in family.targets():
        original = target.path.read_text(encoding="utf-8")
        try:
            updated, added, skipped, repaired = render_content(family, rows, original, target.language)
        except ContentUpdateError as exc:
            raise ContentUpdateError(f"{to_repo_relative(target.path)}: {exc}") from exc
        changed = updated != original
        if apply and changed:
            rewrite_text_file(target.path, lambda _content, updated=updated: updated)
        changes.append(
            PageChange(
                family=family.name,
                path=target.path,
                language=target.language,
                added=added,
                skipped=skipped,
                repaired=repaired,
                changed=changed,
            )
        )
    return changes


def render_cv_family(rows: list[ContentRow], *, apply: bool) -> list[PageChange]:
    changes = []
    detailed_rows = [row for row in rows if cv_targets(row) & {"detailed"}]
    simple_rows = [row for row in rows if cv_targets(row) & {"simple"}]

    for target in FAMILIES["cv"].targets():
        original = target.path.read_text(encoding="utf-8")
        try:
            updated, added, skipped, repaired = render_cv_text(original, detailed_rows, target.language)
        except ContentUpdateError as exc:
            raise ContentUpdateError(f"{to_repo_relative(target.path)}: {exc}") from exc
        changed = updated != original
        if apply and changed:
            rewrite_text_file(target.path, lambda _content, updated=updated: updated)
        changes.append(
            PageChange(
                family="cv",
                path=target.path,
                language=target.language,
                added=added,
                skipped=skipped,
                repaired=repaired,
                changed=changed,
            )
        )

    for language, relative_path in CV_SIMPLE_PATHS.items():
        path = REPO_ROOT / relative_path
        original = path.read_text(encoding="utf-8")
        try:
            updated, added, skipped, repaired = render_cv_simple_text(original, simple_rows, language)
        except ContentUpdateError as exc:
            raise ContentUpdateError(f"{to_repo_relative(path)}: {exc}") from exc
        changed = updated != original
        if apply and changed:
            rewrite_text_file(path, lambda _content, updated=updated: updated)
        changes.append(
            PageChange(
                family="cv",
                path=path,
                language=language,
                added=added,
                skipped=skipped,
                repaired=repaired,
                changed=changed,
            )
        )
    return changes


def render_q315_family(family: FamilyConfig, rows: list[ContentRow], *, apply: bool) -> list[PageChange]:
    if family.name == "cv":
        return render_q315_cv_family(rows, apply=apply)
    target = family.q315_target
    if not target:
        raise ContentUpdateError(f"{family.name}: Q315 source page is not configured")
    original = target.read_text(encoding="utf-8")
    updated, added, skipped, repaired = render_q315_content(family, rows, original)
    changed = updated != original
    if apply and changed:
        rewrite_text_file(target, lambda _content, updated=updated: updated)
    return [
        PageChange(
            family=family.name,
            path=target,
            language="q315",
            added=added,
            skipped=skipped,
            repaired=repaired,
            changed=changed,
        )
    ]


def render_q315_cv_family(rows: list[ContentRow], *, apply: bool) -> list[PageChange]:
    targets = (
        (REPO_ROOT / "Q315/Q3636/Q3646.html", "cv-detailed", [row for row in rows if cv_targets(row) & {"detailed"}], render_q315_cv_text),
        (REPO_ROOT / "Q315/Q3636/index.html", "cv-simple", [row for row in rows if cv_targets(row) & {"simple"}], render_q315_cv_simple_text),
    )
    changes: list[PageChange] = []
    for path, language, target_rows, renderer in targets:
        original = path.read_text(encoding="utf-8")
        updated, added, skipped, repaired = renderer(original, target_rows)
        changed = updated != original
        if apply and changed:
            rewrite_text_file(path, lambda _content, updated=updated: updated)
        changes.append(
            PageChange(
                family="cv",
                path=path,
                language=language,
                added=added,
                skipped=skipped,
                repaired=repaired,
                changed=changed,
            )
        )
    return changes


def render_q315_content(
    family: FamilyConfig,
    rows: list[ContentRow],
    html_content: str,
) -> tuple[str, int, int, int]:
    if family.renderer == "ordered-list":
        return render_block_container(
            html_content,
            tag="ol",
            class_pattern=r"(book-list|media-list|music-list)",
            block_pattern=r"\s*<li\b[\s\S]*?</li>",
            family=family,
            rows=rows,
            language="en",
            build_block=lambda row: build_q315_list_item_html(family, row),
            sort_entries=False,
            repair_block=repair_q315_block,
        )
    if family.renderer == "museum-grid":
        return render_block_container(
            html_content,
            tag="div",
            class_pattern=r"museums-grid",
            block_pattern=r"\s*<article\b[^>]*class=[\"'][^\"']*museum-card[^\"']*[\"'][\s\S]*?</article>",
            family=family,
            rows=rows,
            language="en",
            build_block=build_q315_museum_card_html,
            sort_entries=False,
            repair_block=(
                repair_q315_museum_block
                if museum_entries_are_bindable(rows)
                else repair_q315_block
            ),
        )
    if family.renderer == "quote-grid":
        return render_q315_quotes_text(html_content, rows)
    if family.renderer == "detailed-cv":
        return render_q315_cv_text(html_content, rows)
    raise ContentUpdateError(f"Unsupported Q315 renderer: {family.renderer}")


def render_content(
    family: FamilyConfig,
    rows: list[ContentRow],
    html_content: str,
    language: str,
) -> tuple[str, int, int, int]:
    if not rows:
        return html_content, 0, 0, 0

    return render_content_text(family, rows, html_content, language)


def render_content_text(
    family: FamilyConfig,
    rows: list[ContentRow],
    html_content: str,
    language: str,
) -> tuple[str, int, int, int]:
    if family.renderer == "ordered-list":
        try:
            return render_block_container(
                html_content,
                tag="ol",
                class_pattern=r"(book-list|media-list|music-list)",
                block_pattern=r"\s*<li\b[\s\S]*?</li>",
                family=family,
                rows=rows,
                language=language,
                build_block=lambda row: build_list_item_html(family, row, language),
                sort_entries=family.sort_entries,
            )
        except ContentUpdateError:
            if family.name != "music":
                raise
            return render_block_container(
                html_content,
                tag="ol",
                class_pattern=None,
                block_pattern=r"\s*<li\b[\s\S]*?</li>",
                family=family,
                rows=rows,
                language=language,
                build_block=lambda row: build_list_item_html(family, row, language),
                sort_entries=family.sort_entries,
                requires_pattern=r"typeof=[\"'](?:Person|MusicGroup)[\"']",
            )
    if family.renderer == "museum-grid":
        try:
            return render_block_container(
                html_content,
                tag="div",
                class_pattern=r"museums-grid",
                block_pattern=r"\s*<article\b[^>]*class=[\"'][^\"']*museum-card[^\"']*[\"'][\s\S]*?</article>",
                family=family,
                rows=rows,
                language=language,
                build_block=lambda row: build_museum_card_html(row, language),
                sort_entries=True,
            )
        except ContentUpdateError:
            return render_block_container(
                html_content,
                tag="ol",
                class_pattern=None,
                block_pattern=r"\s*<li\b[\s\S]*?</li>",
                family=family,
                rows=rows,
                language=language,
                build_block=lambda row: build_museum_list_item_html(row, language),
                sort_entries=True,
                requires_pattern=r"class=[\"']museum-type[\"']|typeof=[\"'](?:Museum|ArtGallery)[\"']",
            )
    if family.renderer == "quote-grid":
        return render_quotes_text(html_content, rows, language)
    if family.renderer == "detailed-cv":
        return render_cv_text(html_content, rows, language)
    raise ContentUpdateError(f"Unsupported renderer: {family.renderer}")


def render_block_container(
    html_content: str,
    *,
    tag: str,
    class_pattern: str | None,
    block_pattern: str,
    family: FamilyConfig,
    rows: list[ContentRow],
    language: str,
    build_block,
    sort_entries: bool,
    requires_pattern: str | None = None,
    repair_block=None,
) -> tuple[str, int, int, int]:
    bounds = find_container_bounds(html_content, tag, class_pattern, requires_pattern)
    if not bounds:
        target = class_pattern or requires_pattern or tag
        raise ContentUpdateError(f"{family.name}: container not found for {target}")

    open_start, open_end, close_start, close_end = bounds
    inner = html_content[open_end:close_start]

    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        blocks = extract_blocks(inner, block_pattern)
        match = matching_block(blocks, row, language)
        if match:
            skipped += 1
            start, end, block = match
            repair = repair_block or add_q315_binding
            repaired_block = repair(block, row)
            if repaired_block != block:
                inner = inner[:start] + repaired_block + inner[end:]
                repaired += 1
            continue
        inner = insert_block(inner, block_pattern, build_block(row), sort_entries)
        added += 1

    if added == 0 and repaired == 0:
        return html_content, added, skipped, repaired

    updated = html_content[:open_end] + inner + html_content[close_start:]
    return updated, added, skipped, repaired


def find_container_bounds(
    html_content: str,
    tag: str,
    class_pattern: str | None,
    requires_pattern: str | None = None,
) -> tuple[int, int, int, int] | None:
    open_tag_pattern = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
    for match in open_tag_pattern.finditer(html_content):
        open_tag = match.group(0)
        if class_pattern and not re.search(
            rf"class=[\"'][^\"']*{class_pattern}[^\"']*[\"']",
            open_tag,
            re.IGNORECASE,
        ):
            continue
        bounds = find_matching_close(html_content, tag, match.start(), match.end())
        if not bounds:
            continue
        if requires_pattern and not re.search(
            requires_pattern,
            html_content[bounds[1] : bounds[2]],
            re.IGNORECASE,
        ):
            continue
        return bounds
    return None


def find_matching_close(
    html_content: str,
    tag: str,
    open_start: int,
    open_end: int,
) -> tuple[int, int, int, int] | None:
    token_pattern = re.compile(rf"</?{tag}\b[^>]*>", re.IGNORECASE)
    depth = 1
    for token in token_pattern.finditer(html_content, open_end):
        token_text = token.group(0)
        if token_text.startswith("</"):
            depth -= 1
            if depth == 0:
                return open_start, open_end, token.start(), token.end()
        elif not token_text.endswith("/>"):
            depth += 1
    return None


def extract_blocks(inner: str, block_pattern: str) -> list[tuple[int, int, str]]:
    return [
        (match.start(), match.end(), match.group(0))
        for match in re.finditer(block_pattern, inner, re.IGNORECASE)
    ]


def matching_block(
    blocks: list[tuple[int, int, str]],
    row: ContentRow,
    language: str,
) -> tuple[int, int, str] | None:
    for start, end, block in blocks:
        if block_has_entry(block, row, language):
            return start, end, block
    return None


def insert_block(inner: str, block_pattern: str, block: str, sort_entries: bool) -> str:
    blocks = extract_blocks(inner, block_pattern)
    indent = detect_block_indent(inner, block_pattern)
    block_text = "\n" + indent_block(block.strip(), indent) + "\n"

    if sort_entries:
        new_key = block_sort_key(block)
        for start, _end, existing in blocks:
            if block_sort_key(existing) > new_key:
                return inner[:start] + block_text + inner[start:]

    insert_at = len(inner.rstrip())
    return inner[:insert_at] + block_text + inner[insert_at:]


def detect_block_indent(inner: str, block_pattern: str) -> str:
    block = re.search(block_pattern, inner, re.IGNORECASE)
    if block:
        actual_start = block.start() + len(block.group(0)) - len(block.group(0).lstrip())
        line_start = inner.rfind("\n", 0, actual_start)
        prefix = inner[line_start + 1 : actual_start] if line_start >= 0 else inner[:actual_start]
        if prefix.strip() == "":
            return prefix
    return " " * 16


def indent_block(block: str, indent: str) -> str:
    return "\n".join(f"{indent}{line}" if line else line for line in block.splitlines())


def block_has_entry(block: str, row: ContentRow, language: str) -> bool:
    if row.local_qid and re.search(rf"\blocal:{re.escape(row.local_qid)}\b|\b{re.escape(row.local_qid)}\b", block):
        return True
    if row.wikidata_url and block_has_wikidata_url(block, row.wikidata_url):
        return True
    if row.family == "quotes":
        return False
    expected = normalize_text(row.localized("name", language))
    for value in re.findall(
        r"<span\b[^>]*property=[\"']name[\"'][^>]*>([\s\S]*?)</span>",
        block,
        flags=re.IGNORECASE,
    ):
        if normalize_text(strip_tags(value)) == expected:
            return True
    return False


def q315_binding_attrs(row: ContentRow) -> str:
    if not row.local_qid:
        return ""
    return (
        f' data-q315-source="local:{esc(row.local_qid)}"'
        f' data-q315-function="local:{CONTENT_RENDER_FUNCTION}"'
    )


def block_has_wikidata_url(block: str, wikidata_url: str) -> bool:
    expected = canonical_wikidata_url(wikidata_url)
    for value in re.findall(
        r"<link\b(?=[^>]*property=[\"']sameAs[\"'])[^>]*href=[\"']([^\"']+)[\"']",
        block,
        flags=re.IGNORECASE,
    ):
        if canonical_wikidata_url(html.unescape(value)) == expected:
            return True
    return False


def q315_source_attrs(qid: str) -> str:
    if not qid:
        return ""
    return (
        f' data-q315-source="local:{esc(qid)}"'
        f' data-q315-function="local:{CONTENT_RENDER_FUNCTION}"'
    )


def q315_parts_attrs(row: ContentRow) -> str:
    qids = split_qids(row.data.get("part_qids", ""))
    if not qids:
        return ""
    refs = " ".join(f"local:{qid}" for qid in qids)
    return f' data-q315-parts="{esc(refs)}"'


def split_qids(value: str) -> list[str]:
    qids = re.findall(r"Q[1-9][0-9]*", value)
    return list(dict.fromkeys(qids))


def add_q315_binding(block: str, row: ContentRow) -> str:
    attrs = q315_binding_attrs(row)
    opening_tag = re.search(r"<(?:li|article|div)\b[^>]*>", block)
    if not attrs or (opening_tag and "data-q315-source=" in opening_tag.group(0)):
        return block
    return re.sub(r"(<(?:li|article|div)\b[^>]*)(>)", rf"\1{attrs}\2", block, count=1)


def repair_q315_block(block: str, row: ContentRow) -> str:
    if not row.local_qid or row.local_qid in block:
        return block
    if row.wikidata_url and row.wikidata_url not in block:
        return block
    content_attr = f'data-content="local:{esc(row.local_qid)}"'
    name_span = re.search(
        r"<span\b(?=[^>]*property=[\"']name[\"'])[^>]*>[\s\S]*?</span>",
        block,
        flags=re.IGNORECASE,
    )
    if name_span:
        span = name_span.group(0)
        if re.search(r"data-content=[\"']local:Q[1-9][0-9]*[\"']", span):
            repaired = re.sub(
                r"data-content=[\"']local:Q[1-9][0-9]*[\"']",
                content_attr,
                span,
                count=1,
            )
        else:
            repaired = re.sub(
                r"(<span\b[^>]*property=[\"']name[\"'][^>]*)(>)",
                rf"\1 {content_attr}\2",
                span,
                count=1,
                flags=re.IGNORECASE,
            )
        repaired = re.sub(r">[\s\S]*?</span>$", f">{esc(row.local_qid)}</span>", repaired)
        return block[: name_span.start()] + repaired + block[name_span.end() :]
    if re.search(r"data-content=[\"']local:Q[1-9][0-9]*[\"']", block):
        return re.sub(
            r"data-content=[\"']local:Q[1-9][0-9]*[\"']",
            content_attr,
            block,
            count=1,
        )
    return block


def repair_q315_museum_block(block: str, row: ContentRow) -> str:
    """Bind the museum name heading.

    Older sources wrote the heading as bare QID text -- ``<h2 class="museum-name"
    typeof="Museum">Q3792</h2>`` -- with no ``data-content``, so the renderer had
    nothing to substitute a per-language label into and the literal QID would
    reach the page. The QID already being present as text is exactly why the
    generic repair skips these blocks, so handle the heading first.
    """
    if row.local_qid and row.local_qid not in UNBOUND_CONTENT_QIDS:
        block = bind_first_tag(block, r"h2", r"museum-name", row.local_qid)
    return repair_q315_block(block, row)


def bind_first_tag(block: str, tag: str, class_name: str, qid: str) -> str:
    """Add ``data-content="local:<qid>"`` to the first matching unbound tag."""
    match = re.search(
        rf"<{tag}\b[^>]*class=[\"'][^\"']*{class_name}[^\"']*[\"'][^>]*>",
        block,
        re.IGNORECASE,
    )
    if not match or "data-content=" in match.group(0):
        return block
    insert_at = match.end() - 1
    return block[:insert_at] + f' data-content="local:{esc(qid)}"' + block[insert_at:]


def add_attrs_to_first_tag(block: str, tag: str, class_name: str, attrs: str) -> str:
    if not attrs:
        return block
    pattern = (
        rf"(<{tag}\b(?=[^>]*class=[\"'][^\"']*{re.escape(class_name)}[^\"']*[\"'])"
        r"(?!(?=[^>]*data-q315-source=))(?!(?=[^>]*data-q315-parts=))[^>]*)(>)"
    )
    return re.sub(pattern, rf"\1{attrs}\2", block, count=1, flags=re.IGNORECASE)


def add_quote_bindings(block: str, row: ContentRow) -> str:
    updated = add_q315_binding(block, row)
    quote_attrs = q315_parts_attrs(row)
    updated = add_attrs_to_first_tag(updated, "p", "quote-text", quote_attrs)
    attribution_qid = row.data.get("attribution_qid", "").strip()
    updated = add_attrs_to_first_tag(
        updated,
        "p",
        "quote-author",
        q315_source_attrs(attribution_qid),
    )
    return updated


def block_sort_key(block: str) -> str:
    match = re.search(
        r"<span\b[^>]*property=[\"']name[\"'][^>]*>([\s\S]*?)</span>",
        block,
        flags=re.IGNORECASE,
    )
    return normalize_text(strip_tags(match.group(1))) if match else normalize_text(block)


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(value))


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def build_list_item_html(family: FamilyConfig, row: ContentRow, language: str) -> str:
    name = esc(row.localized("name", language))
    item_type = esc(row.item_type)
    class_attr = ' class="book-item"' if family.name == "books" else ""
    wrapper_class = ' class="book-title"' if family.name == "books" else ""
    parts = [
        f'<li property="itemListElement" typeof="ListItem"{class_attr}{q315_binding_attrs(row)}>',
        f'    <span{wrapper_class} typeof="{item_type}">',
        f'        <span property="name">{name}</span>',
        "    </span>",
    ]
    if row.wikidata_url:
        parts.append(f'    <link property="sameAs" href="{esc(row.wikidata_url)}" />')
    if family.name == "books":
        creator = row.localized("creator", language, required=False)
        if creator:
            parts.append(f'    <span class="book-author">{esc(creator)}</span>')
    parts.append("</li>")
    return "\n".join(parts)


def build_q315_list_item_html(family: FamilyConfig, row: ContentRow) -> str:
    ensure_local_qid(row)
    item_type = esc(row.item_type)
    class_attr = ' class="book-item"' if family.name == "books" else ""
    wrapper_class = ' class="book-title"' if family.name == "books" else ""
    parts = [
        f'<li property="itemListElement" typeof="ListItem"{class_attr}>',
        f'    <span{wrapper_class} typeof="{item_type}">',
        f'        <span property="name" data-content="local:{esc(row.local_qid)}">{esc(row.local_qid)}</span>',
    ]
    if row.wikidata_url:
        parts.append(f'        <link property="sameAs" href="{esc(row.wikidata_url)}" />')
    parts.append("    </span>")
    if family.name == "books":
        creator_qid = row.data.get("creator_qid", "").strip()
        creator = row.localized("creator", "en", required=False)
        if creator_qid:
            parts.append(f'    <span class="book-author" data-content="local:{esc(creator_qid)}">{esc(creator_qid)}</span>')
        elif creator:
            parts.append(f'    <span class="book-author">{esc(creator)}</span>')
    parts.append("</li>")
    return "\n".join(parts)


def build_museum_card_html(row: ContentRow, language: str) -> str:
    type_label = row.localized("type_label", language, required=False) or row.item_type
    return "\n".join(
        [
            f'<article class="museum-card"{q315_binding_attrs(row)}>',
            '    <div class="museum-icon"></div>',
            f'    <h2 class="museum-name" typeof="{esc(row.item_type)}">',
            f'        <span property="name">{esc(row.localized("name", language))}</span>',
            f'        <link property="sameAs" href="{esc(row.wikidata_url)}" />',
            "    </h2>",
            f'    <span class="museum-type">{esc(type_label)}</span>',
            "</article>",
        ]
    )


def build_q315_museum_card_html(row: ContentRow) -> str:
    ensure_local_qid(row)
    return "\n".join(
        [
            '<article class="museum-card">',
            '    <div class="museum-icon"></div>',
            f'    <h2 class="museum-name" typeof="{esc(row.item_type)}"'
            f'{museum_name_binding(row)}>{esc(row.local_qid)}</h2>',
            f'    <link property="sameAs" href="{esc(row.wikidata_url)}" />',
            f'    <span class="museum-type" data-content="local:{museum_type_label_qid(row)}">{museum_type_label_qid(row)}</span>',
            "</article>",
        ]
    )


def build_museum_list_item_html(row: ContentRow, language: str) -> str:
    type_label = row.localized("type_label", language, required=False) or row.item_type
    return "\n".join(
        [
            f'<li property="itemListElement" typeof="ListItem"{q315_binding_attrs(row)}>',
            f'    <span typeof="{esc(row.item_type)}">',
            f'        <span property="name">{esc(row.localized("name", language))}</span>',
            f'        <link property="sameAs" href="{esc(row.wikidata_url)}" />',
            "    </span>",
            f'    <span class="museum-type">{esc(type_label)}</span>',
            "</li>",
        ]
    )


def ensure_local_qid(row: ContentRow) -> None:
    if not row.local_qid:
        raise ContentUpdateError(f"{row.family}:{row.row_number}: local_qid is required for Q315 source updates")


def museum_entries_are_bindable(rows: list[ContentRow]) -> bool:
    """True when every museum can be bound, so the grid can be bound as a whole."""
    return not any(row.local_qid in UNBOUND_CONTENT_QIDS for row in rows)


def museum_name_binding(row: ContentRow) -> str:
    if row.local_qid in UNBOUND_CONTENT_QIDS:
        return ""
    return f' data-content="local:{esc(row.local_qid)}"'


def museum_type_label_qid(row: ContentRow) -> str:
    if row.item_type == "ArtGallery":
        return "Q7478"
    return "Q3351"


def render_quotes_text(
    html_content: str,
    rows: list[ContentRow],
    language: str,
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        section_bounds = find_quote_section_bounds(updated, row, language)
        if not section_bounds:
            expected = row.localized("category", language)
            raise ContentUpdateError(
                f"quotes:{row.row_number}: category section not found for {language}: {expected}"
            )
        section_start, _section_open_end, section_close_start, _section_close_end = section_bounds
        section_html = updated[section_start:section_close_start]
        grid_bounds = find_container_bounds(section_html, "div", r"quotes-grid")
        if not grid_bounds:
            raise ContentUpdateError(f"quotes:{row.row_number}: quotes-grid missing for category")
        grid_open_start, grid_open_end, grid_close_start, _grid_close_end = grid_bounds
        grid_inner = section_html[grid_open_end:grid_close_start]
        repaired_inner = repair_existing_quote_card(grid_inner, row, language)
        if repaired_inner != grid_inner:
            skipped += 1
            repaired += 1
            section_html = (
                section_html[:grid_open_end]
                + repaired_inner
                + section_html[grid_close_start:]
            )
            updated = updated[:section_start] + section_html + updated[section_close_start:]
            continue
        if quote_exists(grid_inner, row, language):
            skipped += 1
            continue
        indent = detect_block_indent(grid_inner, r"<div\b[^>]*class=[\"'][^\"']*quote-card")
        block = indent_block(build_quote_card_html(row, language), indent)
        replacement = grid_inner.rstrip() + "\n" + block + "\n" + indent[:-4 if len(indent) >= 4 else 0]
        section_html = (
            section_html[:grid_open_end]
            + replacement
            + section_html[grid_close_start:]
        )
        updated = updated[:section_start] + section_html + updated[section_close_start:]
        added += 1
    return updated, added, skipped, repaired


def render_q315_quotes_text(
    html_content: str,
    rows: list[ContentRow],
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        ensure_local_qid(row)
        if row.local_qid in updated:
            skipped += 1
            repaired_text = repair_q315_quote_attribution(updated, row)
            if repaired_text != updated:
                updated = repaired_text
                repaired += 1
            continue
        section_bounds = find_quote_section_bounds(updated, row, "en")
        if not section_bounds:
            expected = row.localized("category", "en")
            raise ContentUpdateError(
                f"quotes:{row.row_number}: Q315 category section not found: {expected}"
            )
        section_start, _section_open_end, section_close_start, _section_close_end = section_bounds
        section_html = updated[section_start:section_close_start]
        grid_bounds = find_container_bounds(section_html, "div", r"quotes-grid")
        if not grid_bounds:
            raise ContentUpdateError(f"quotes:{row.row_number}: Q315 quotes-grid missing")
        grid_open_start, grid_open_end, grid_close_start, _grid_close_end = grid_bounds
        grid_inner = section_html[grid_open_end:grid_close_start]
        indent = detect_block_indent(grid_inner, r"<div\b[^>]*class=[\"'][^\"']*quote-card")
        block = indent_block(build_q315_quote_card_html(row), indent)
        replacement = grid_inner.rstrip() + "\n" + block + "\n" + indent[:-4 if len(indent) >= 4 else 0]
        section_html = (
            section_html[:grid_open_end]
            + replacement
            + section_html[grid_close_start:]
        )
        updated = updated[:section_start] + section_html + updated[section_close_start:]
        added += 1
    return updated, added, skipped, repaired


def repair_q315_quote_attribution(html_content: str, row: ContentRow) -> str:
    """Bind a quote's author line when the source wrote it as bare QID text.

    Split quotes predate the ``attribution_qid`` column, so their author line was
    authored as ``<p class="quote-author">Q6325</p>`` with no binding and the
    renderer had no label to substitute per language.
    """
    attribution_qid = row.data.get("attribution_qid", "").strip()
    if not re.fullmatch(r"Q[1-9][0-9]*", attribution_qid):
        return html_content
    card = find_quote_card_bounds(html_content, row)
    if not card:
        return html_content
    start, end = card
    block = html_content[start:end]
    bound = bind_first_tag(block, r"p", r"quote-author", attribution_qid)
    if bound == block:
        return html_content
    return html_content[:start] + bound + html_content[end:]


def find_quote_card_bounds(html_content: str, row: ContentRow) -> tuple[int, int] | None:
    """Locate the quote card that carries this row's content binding."""
    for match in re.finditer(
        r"<div\b[^>]*class=[\"'][^\"']*quote-card[^\"']*[\"'][^>]*>", html_content
    ):
        bounds = find_matching_close(html_content, "div", match.start(), match.end())
        if not bounds:
            continue
        card = html_content[bounds[0] : bounds[3]]
        if re.search(rf"local:{re.escape(row.local_qid)}\b", card):
            return bounds[0], bounds[3]
    return None


def find_quote_section_bounds(
    html_content: str,
    row: ContentRow,
    language: str,
) -> tuple[int, int, int, int] | None:
    expected = quote_category_labels(row, language)
    for match in re.finditer(r"<section\b[^>]*class=[\"'][^\"']*quote-section[^\"']*[\"'][^>]*>", html_content):
        bounds = find_matching_close(html_content, "section", match.start(), match.end())
        if not bounds:
            continue
        section_html = html_content[bounds[1] : bounds[2]]
        heading = re.search(
            r"<h[23]\b[^>]*class=[\"'][^\"']*section-title[^\"']*[\"'][^>]*>([\s\S]*?)</h[23]>",
            section_html,
            flags=re.IGNORECASE,
        )
        if heading and strip_tags(heading.group(1)).strip() in expected:
            return bounds
    return None


def quote_category_labels(row: ContentRow, language: str) -> set[str]:
    labels = {
        row.data.get(f"category_{language}", "").strip(),
        row.data.get("category", "").strip(),
        row.data.get("category_en", "").strip(),
    }
    return {label for label in labels if label}


def quote_exists(grid_inner: str, row: ContentRow, language: str) -> bool:
    expected_quote = normalize_text(row.localized("quote", language))
    expected_attribution = normalize_text(row.localized("attribution", language))
    for card in re.findall(
        r"<div\b[^>]*class=[\"'][^\"']*quote-card[^\"']*[\"'][\s\S]*?</div>",
        grid_inner,
        flags=re.IGNORECASE,
    ):
        quote = re.search(r"<p\b[^>]*class=[\"'][^\"']*quote-text[^\"']*[\"'][^>]*>([\s\S]*?)</p>", card)
        attribution = re.search(r"<p\b[^>]*class=[\"'][^\"']*quote-author[^\"']*[\"'][^>]*>([\s\S]*?)</p>", card)
        if quote and attribution:
            if (
                normalize_text(strip_tags(quote.group(1))) == expected_quote
                and normalize_text(strip_tags(attribution.group(1))) == expected_attribution
            ):
                return True
    return False


def repair_existing_quote_card(grid_inner: str, row: ContentRow, language: str) -> str:
    for match in re.finditer(
        r"<div\b[^>]*class=[\"'][^\"']*quote-card[^\"']*[\"'][\s\S]*?</div>",
        grid_inner,
        flags=re.IGNORECASE,
    ):
        card = match.group(0)
        if quote_card_matches(card, row, language):
            repaired = add_quote_bindings(card, row)
            if repaired != card:
                return grid_inner[: match.start()] + repaired + grid_inner[match.end() :]
            return grid_inner
    return grid_inner


def quote_card_matches(card: str, row: ContentRow, language: str) -> bool:
    expected_quote = normalize_text(row.localized("quote", language))
    expected_attribution = normalize_text(row.localized("attribution", language))
    quote = re.search(r"<p\b[^>]*class=[\"'][^\"']*quote-text[^\"']*[\"'][^>]*>([\s\S]*?)</p>", card)
    attribution = re.search(r"<p\b[^>]*class=[\"'][^\"']*quote-author[^\"']*[\"'][^>]*>([\s\S]*?)</p>", card)
    return bool(
        quote
        and attribution
        and normalize_text(strip_tags(quote.group(1))) == expected_quote
        and normalize_text(strip_tags(attribution.group(1))) == expected_attribution
    )


def build_quote_card_html(row: ContentRow, language: str) -> str:
    return "\n".join(
        [
            f'<div class="quote-card"{q315_binding_attrs(row)}>',
            f'    <p class="quote-text"{q315_parts_attrs(row)}>{esc(row.localized("quote", language))}</p>',
            f'    <p class="quote-author"{q315_source_attrs(row.data.get("attribution_qid", "").strip())}>{esc(row.localized("attribution", language))}</p>',
            "</div>",
        ]
    )


def build_q315_quote_card_html(row: ContentRow) -> str:
    ensure_local_qid(row)
    attribution_qid = row.data.get("attribution_qid", "").strip()
    author_attrs = f' data-content="local:{esc(attribution_qid)}"' if attribution_qid else ""
    author_text = attribution_qid or row.localized("attribution", "en")
    quote_lines = [
        f'<div class="quote-card">',
        f'    <p class="quote-text" data-content="local:{esc(row.local_qid)}">',
    ]
    part_qids = split_qids(row.data.get("part_qids", ""))
    if part_qids:
        quote_lines.extend(
            [
                f'        <q-call data-function="local:{CONTENT_RENDER_FUNCTION}">',
                '            <q-arg data-name="parts">',
            ]
        )
        quote_lines.extend(
            f'                <span data-content="local:{esc(qid)}">{esc(qid)}</span>'
            for qid in part_qids
        )
        quote_lines.extend(
            [
                "            </q-arg>",
                "        </q-call>",
                "    </p>",
            ]
        )
    else:
        quote_lines[-1] += f'{esc(row.local_qid)}</p>'
    quote_lines.append(f'    <p class="quote-author"{author_attrs}>{esc(author_text)}</p>')
    quote_lines.append("</div>")
    return "\n".join(quote_lines)


def render_q315_cv_text(
    html_content: str,
    rows: list[ContentRow],
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        ensure_local_qid(row)
        if cv_entry_exists(updated, row):
            skipped += 1
            continue
        section_bounds = find_cv_section_bounds(updated, row)
        if not section_bounds:
            raise ContentUpdateError(
                f"cv:{row.row_number}: section not found: {row.data.get('section', '').strip()}"
            )
        _section_start, section_open_end, section_close_start, _section_close_end = section_bounds
        section_html = updated[section_open_end:section_close_start]
        replacement = insert_cv_entry(
            section_html,
            row,
            build_q315_cv_entry_html(row),
            cv_year_heading_html(row, q315=True),
        )
        updated = updated[:section_open_end] + replacement + updated[section_close_start:]
        added += 1
    return updated, added, skipped, repaired


def render_q315_cv_simple_text(
    html_content: str,
    rows: list[ContentRow],
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        simple_qid = cv_simple_local_qid(row)
        if simple_qid and re.search(rf"\blocal:{re.escape(simple_qid)}\b|\b{re.escape(simple_qid)}\b", updated):
            skipped += 1
            continue
        if not simple_qid:
            raise ContentUpdateError(f"cv:{row.row_number}: simple_local_qid is required for simple CV updates")
        grid_bounds = find_cv_simple_grid_bounds(updated, row)
        if not grid_bounds:
            raise ContentUpdateError(
                f"cv:{row.row_number}: simple CV section not found: {row.data.get('section', '').strip()}"
            )
        grid_open_start, grid_open_end, grid_close_start, _grid_close_end = grid_bounds
        grid_inner = updated[grid_open_end:grid_close_start]
        block = build_q315_cv_simple_card_html(row)
        replacement = insert_cv_simple_card(grid_inner, row, block)
        updated = updated[:grid_open_end] + replacement + updated[grid_close_start:]
        added += 1
    return updated, added, skipped, repaired


def render_cv_simple_text(
    html_content: str,
    rows: list[ContentRow],
    language: str,
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        if cv_simple_entry_exists(updated, row, language=language):
            skipped += 1
            continue
        simple_qid = cv_simple_local_qid(row)
        if not simple_qid:
            raise ContentUpdateError(f"cv:{row.row_number}: simple_local_qid is required for simple CV updates")
        grid_bounds = find_cv_simple_grid_bounds(updated, row)
        if not grid_bounds:
            raise ContentUpdateError(
                f"cv:{row.row_number}: simple CV section not found: {row.data.get('section', '').strip()}"
            )
        _grid_open_start, grid_open_end, grid_close_start, _grid_close_end = grid_bounds
        grid_inner = updated[grid_open_end:grid_close_start]
        block = build_cv_simple_card_html(row, language)
        replacement = insert_cv_simple_card(grid_inner, row, block)
        updated = updated[:grid_open_end] + replacement + updated[grid_close_start:]
        added += 1
    return updated, added, skipped, repaired


def cv_simple_entry_exists(html_content: str, row: ContentRow, *, language: str) -> bool:
    simple_qid = cv_simple_local_qid(row)
    if simple_qid and re.search(rf"\blocal:{re.escape(simple_qid)}\b|\b{re.escape(simple_qid)}\b", html_content):
        return True
    expected = normalize_text(cv_simple_content(row, language))
    return bool(expected and normalize_text(strip_tags(html_content)).find(expected) >= 0)


def find_cv_simple_grid_bounds(html_content: str, row: ContentRow) -> tuple[int, int, int, int] | None:
    section_id = row.data.get("section", "").strip()
    if not section_id:
        return None
    header = re.search(
        rf"<div\b(?=[^>]*class=[\"'][^\"']*section-header[^\"']*[\"'])(?=[^>]*\bid=[\"']{re.escape(section_id)}[\"'])[^>]*>",
        html_content,
        flags=re.IGNORECASE,
    )
    if not header:
        return None
    for match in re.finditer(r"<div\b[^>]*>", html_content[header.end() :], flags=re.IGNORECASE):
        start = header.end() + match.start()
        open_tag = match.group(0)
        if re.search(r"class=[\"'][^\"']*bento-grid[^\"']*[\"']", open_tag, flags=re.IGNORECASE):
            return find_matching_close(html_content, "div", start, start + len(open_tag))
    return None


def build_q315_cv_simple_card_html(row: ContentRow) -> str:
    body = q315_cv_content_html(
        "p",
        "",
        cv_simple_local_qid(row),
        split_qids(row.data.get("part_qids", "")),
    )
    return "\n".join(
        [
            '<div class="bento-card">',
            f'    <h3>{esc(cv_year_key(row))}</h3>',
            indent_block(body, "    "),
            "</div>",
        ]
    )


def build_cv_simple_card_html(row: ContentRow, language: str) -> str:
    simple_qid = cv_simple_local_qid(row)
    attrs = q315_source_attrs(simple_qid)
    body = f'<p{attrs}>{cv_content_html(row, language, content=cv_simple_content(row, language))}</p>'
    return "\n".join(
        [
            '<div class="bento-card">',
            f'    <h3><span class="year-badge">{esc(cv_year_value(row, language=language))}</span></h3>',
            indent_block(body, "    "),
            "</div>",
        ]
    )


def insert_cv_simple_card(grid_inner: str, row: ContentRow, block: str) -> str:
    card_pattern = r"\s*<div\b[^>]*class=[\"'][^\"']*bento-card[^\"']*[\"'][\s\S]*?</div>"
    new_year_number = cv_year_number(cv_year_value(row)) or cv_year_number(cv_year_key(row))
    if new_year_number is not None:
        for match in re.finditer(card_pattern, grid_inner, flags=re.IGNORECASE):
            heading = re.search(r"<h3\b[^>]*>([\s\S]*?)</h3>", match.group(0), flags=re.IGNORECASE)
            if not heading:
                continue
            existing_year_number = cv_year_number(strip_tags(heading.group(1)).strip())
            if existing_year_number is not None and existing_year_number < new_year_number:
                indent_match = re.search(r"\n([ \t]*)<div\b", match.group(0))
                indent = indent_match.group(1) if indent_match else " " * 16
                insertion = "\n" + indent_block(block.strip(), indent)
                return grid_inner[: match.start()] + insertion + grid_inner[match.start() :]
    return insert_block(grid_inner, card_pattern, block, False)


def render_cv_text(
    html_content: str,
    rows: list[ContentRow],
    language: str,
) -> tuple[str, int, int, int]:
    updated = html_content
    added = 0
    skipped = 0
    repaired = 0
    for row in rows:
        if cv_entry_exists(updated, row, language=language):
            skipped += 1
            continue
        section_bounds = find_cv_section_bounds(updated, row)
        if not section_bounds:
            raise ContentUpdateError(
                f"cv:{row.row_number}: section not found: {row.data.get('section', '').strip()}"
            )
        _section_start, section_open_end, section_close_start, _section_close_end = section_bounds
        section_html = updated[section_open_end:section_close_start]
        replacement = insert_cv_entry(
            section_html,
            row,
            build_cv_entry_html(row, language),
            cv_year_heading_html(row, language=language),
        )
        updated = updated[:section_open_end] + replacement + updated[section_close_start:]
        added += 1
    return updated, added, skipped, repaired


def cv_targets(row: ContentRow) -> set[str]:
    target = row.data.get("target", "").strip().casefold() or "both"
    if target in {"both", "all"}:
        return {"detailed", "simple"}
    if target in {"detailed", "detail", "cv-detailed"}:
        return {"detailed"}
    if target in {"simple", "concise", "cv-simple"}:
        return {"simple"}
    raise ContentUpdateError(f"cv:{row.row_number}: target must be detailed, simple, or both")


def cv_simple_local_qid(row: ContentRow) -> str:
    return row.data.get("simple_local_qid", "").strip()


def find_cv_section_bounds(html_content: str, row: ContentRow) -> tuple[int, int, int, int] | None:
    section_id = row.data.get("section", "").strip()
    if not section_id:
        return None
    for match in re.finditer(r"<section\b[^>]*>", html_content, flags=re.IGNORECASE):
        open_tag = match.group(0)
        if not re.search(rf"\bid=[\"']{re.escape(section_id)}[\"']", open_tag):
            continue
        return find_matching_close(html_content, "section", match.start(), match.end())
    return None


def cv_entry_exists(html_content: str, row: ContentRow, *, language: str = "en") -> bool:
    if row.local_qid and re.search(rf"\blocal:{re.escape(row.local_qid)}\b|\b{re.escape(row.local_qid)}\b", html_content):
        return True
    expected = normalize_text(cv_content(row, language))
    return bool(expected and normalize_text(strip_tags(html_content)).find(expected) >= 0)


def insert_cv_entry(
    section_html: str,
    row: ContentRow,
    entry_html: str,
    heading_html: str,
) -> str:
    year_key = cv_year_key(row)
    year = cv_year_value(row)
    year_blocks = cv_year_blocks(section_html)
    indent = detect_block_indent(section_html, r"<p\b[^>]*class=[\"'][^\"']*conference")
    if not indent:
        indent = " " * 20
    entry = "\n" + indent_block(entry_html.strip(), indent) + "\n"

    for start, open_end, next_start, _block, existing_year in year_blocks:
        if existing_year == year_key or existing_year == year:
            return section_html[:next_start] + entry + section_html[next_start:]

    heading = "\n" + indent_block(heading_html.strip(), indent) + entry
    new_year_number = cv_year_number(year)
    for start, _open_end, _next_start, _block, existing_year in year_blocks:
        existing_number = cv_year_number(existing_year)
        if new_year_number is not None and existing_number is not None and existing_number < new_year_number:
            return section_html[:start] + heading + section_html[start:]

    insert_at = len(section_html.rstrip())
    return section_html[:insert_at] + heading + section_html[insert_at:]


def cv_year_blocks(section_html: str) -> list[tuple[int, int, int, str, str]]:
    headings = list(
        re.finditer(
            r"<h4\b(?=[^>]*class=[\"'][^\"']*year[^\"']*[\"'])[^>]*>([\s\S]*?)</h4>",
            section_html,
            flags=re.IGNORECASE,
        )
    )
    blocks: list[tuple[int, int, int, str, str]] = []
    for index, heading in enumerate(headings):
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(section_html.rstrip())
        label = strip_tags(heading.group(1)).strip()
        blocks.append((heading.start(), heading.end(), next_start, section_html[heading.start():next_start], label))
    return blocks


def build_q315_cv_entry_html(row: ContentRow) -> str:
    ensure_local_qid(row)
    return q315_cv_content_html("p", "conference", row.local_qid, split_qids(row.data.get("part_qids", "")))


def q315_cv_content_html(
    tag: str,
    css_class: str,
    qid: str,
    part_qids: list[str],
) -> str:
    if not part_qids:
        class_attr = f' class="{esc(css_class)}"' if css_class else ""
        return f'<{tag}{class_attr} data-content="local:{esc(qid)}">{esc(qid)}</{tag}>'
    class_attr = f' class="{esc(css_class)}"' if css_class else ""
    lines = [
        f'<{tag}{class_attr} data-content="local:{esc(qid)}">',
        f'    <q-call data-function="local:{CONTENT_RENDER_FUNCTION}">',
        '        <q-arg data-name="parts">',
    ]
    lines.extend(
        f'            <span data-content="local:{esc(part_qid)}">{esc(part_qid)}</span>'
        for part_qid in part_qids
    )
    lines.extend(['        </q-arg>', '    </q-call>', f'</{tag}>'])
    return "\n".join(lines)


def build_cv_entry_html(row: ContentRow, language: str) -> str:
    attrs = q315_binding_attrs(row)
    return f'<p class="conference"{attrs}>{cv_content_html(row, language)}</p>'


def cv_content_html(row: ContentRow, language: str, *, content: str | None = None) -> str:
    content = cv_content(row, language) if content is None else content
    match = TRAILING_URL_RE.search(content)
    href = ""
    if match:
        href = match.group(1)
        content = content[:match.start()].rstrip(" ,")
    if split_qids(row.data.get("part_qids", "")):
        body_html = esc(content)
        if href:
            body_html += f' (<a href="{esc(href)}">{esc(LINK_TEXT.get(language, "Link"))}</a>)'
        return body_html
    title, separator, rest = content.partition(",")
    title_html = f"<b>{esc(title.strip())}</b>" if title.strip() else ""
    body_html = f"{title_html}{esc(separator + rest)}"
    if href:
        body_html += f' (<a href="{esc(href)}">{esc(LINK_TEXT.get(language, "Link"))}</a>)'
    return body_html


def cv_year_heading_html(row: ContentRow, *, q315: bool = False, language: str = "en") -> str:
    if q315:
        return f'<h4 class="year">{esc(cv_year_key(row))}</h4>'
    return f'<h4 class="year">{esc(cv_year_value(row, language=language))}</h4>'


def cv_content(row: ContentRow, language: str) -> str:
    value = row.data.get(f"content_{language}", "").strip()
    if not value:
        value = row.data.get("content", "").strip()
    if not value:
        value = row.data.get("content_en", "").strip()
    if not value:
        raise ContentUpdateError(f"{row.family}:{row.row_number}: missing content")
    return value


def cv_simple_content(row: ContentRow, language: str) -> str:
    value = row.data.get(f"simple_content_{language}", "").strip()
    if not value:
        value = row.data.get("simple_content", "").strip()
    return value or cv_content(row, language)


def cv_year_key(row: ContentRow) -> str:
    year_qid = row.data.get("year_qid", "").strip()
    if year_qid:
        return year_qid
    year = row.data.get("year", "").strip()
    qid = cv_year_qid(year)
    if not qid:
        raise ContentUpdateError(
            f"cv:{row.row_number}: no local year QID found for {year}; fill year_qid"
        )
    return qid


def cv_year_value(row: ContentRow, *, language: str = "en") -> str:
    year = row.data.get("year", "").strip()
    if year:
        return year
    year_qid = row.data.get("year_qid", "").strip()
    return cv_year_label(year_qid, language) or year_qid


def cv_year_number(value: str) -> int | None:
    label = cv_year_label(value, "en") if re.fullmatch(r"Q[1-9][0-9]*", value) else value
    return int(label) if re.fullmatch(r"[12][0-9]{3}", label or "") else None


def cv_year_qid(year: str) -> str:
    if not year:
        return ""
    for qid, row in cv_year_labels().items():
        if row.get("en", "").strip() == year:
            return qid
    return ""


def cv_year_label(qid: str, language: str) -> str:
    if not qid:
        return ""
    row = cv_year_labels().get(qid, {})
    return row.get(language, "").strip() or row.get("en", "").strip()


_CV_YEAR_LABELS: dict[str, dict[str, str]] | None = None


def cv_year_labels() -> dict[str, dict[str, str]]:
    global _CV_YEAR_LABELS
    if _CV_YEAR_LABELS is not None:
        return _CV_YEAR_LABELS
    path = REPO_ROOT / "src/main/abstract/data/labels-wikibase.csv"
    labels: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            value = row.get("en", "").strip()
            if re.fullmatch(r"[12][0-9]{3}", value):
                labels[row["identifier"]] = row
    _CV_YEAR_LABELS = labels
    return labels


def render_content_with_beautifulsoup(
    family: FamilyConfig,
    rows: list[ContentRow],
    html_content: str,
    language: str,
) -> tuple[str, int, int]:
    soup = BeautifulSoup(html_content, features="html.parser")
    if family.renderer == "ordered-list":
        added, skipped = render_ordered_list(soup, family, rows, language)
    elif family.renderer == "museum-grid":
        added, skipped = render_museum_grid(soup, rows, language)
    elif family.renderer == "quote-grid":
        added, skipped = render_quote_grid(soup, rows, language)
    else:
        raise ContentUpdateError(f"Unsupported renderer: {family.renderer}")
    return str(soup), added, skipped


def render_ordered_list(
    soup: BeautifulSoup,
    family: FamilyConfig,
    rows: list[ContentRow],
    language: str,
) -> tuple[int, int]:
    ordered_list = soup.find("ol", class_=re.compile(r"(book-list|media-list|music-list)"))
    if not isinstance(ordered_list, Tag):
        raise ContentUpdateError(f"{family.name}: ordered list target not found")

    added = 0
    skipped = 0
    for row in rows:
        if has_existing_entry(ordered_list, row, language):
            skipped += 1
            continue
        ordered_list.append(soup.new_string("\n"))
        ordered_list.append(build_list_item(soup, family, row, language))
        ordered_list.append(soup.new_string("\n"))
        added += 1

    if family.sort_entries:
        sort_children_by_name(ordered_list)
    return added, skipped


def build_list_item(
    soup: BeautifulSoup,
    family: FamilyConfig,
    row: ContentRow,
    language: str,
) -> Tag:
    li = soup.new_tag("li")
    li["property"] = "itemListElement"
    li["typeof"] = "ListItem"
    if family.name == "books":
        li["class"] = "book-item"

    wrapper = soup.new_tag("span")
    wrapper["typeof"] = row.item_type

    name = soup.new_tag("span")
    name["property"] = "name"
    name.string = row.localized("name", language)

    if family.name == "books":
        wrapper["class"] = "book-title"

    wrapper.append(name)
    li.append(wrapper)

    if row.wikidata_url:
        link = soup.new_tag("link")
        link["property"] = "sameAs"
        link["href"] = row.wikidata_url
        li.append(soup.new_string("\n"))
        li.append(link)

    if family.name == "books":
        creator_text = row.localized("creator", language, required=False)
        if creator_text:
            creator = soup.new_tag("span")
            creator["class"] = "book-author"
            creator.string = creator_text
            li.append(soup.new_string("\n"))
            li.append(creator)

    return li


def render_museum_grid(
    soup: BeautifulSoup,
    rows: list[ContentRow],
    language: str,
) -> tuple[int, int]:
    grid = soup.find("div", class_="museums-grid")
    if not isinstance(grid, Tag):
        return render_museum_ordered_list(soup, rows, language)

    added = 0
    skipped = 0
    for row in rows:
        if has_existing_entry(grid, row, language):
            skipped += 1
            continue
        grid.append(soup.new_string("\n"))
        grid.append(build_museum_card(soup, row, language))
        grid.append(soup.new_string("\n"))
        added += 1

    sort_children_by_name(grid)
    return added, skipped


def render_museum_ordered_list(
    soup: BeautifulSoup,
    rows: list[ContentRow],
    language: str,
) -> tuple[int, int]:
    ordered_list = find_museum_ordered_list(soup)
    if not ordered_list:
        raise ContentUpdateError("museums: museums-grid or museum ordered list target not found")

    added = 0
    skipped = 0
    for row in rows:
        if has_existing_entry(ordered_list, row, language):
            skipped += 1
            continue
        ordered_list.append(soup.new_string("\n"))
        ordered_list.append(build_museum_list_item(soup, row, language))
        ordered_list.append(soup.new_string("\n"))
        added += 1

    sort_children_by_name(ordered_list)
    return added, skipped


def find_museum_ordered_list(soup: BeautifulSoup) -> Tag | None:
    for ordered_list in soup.find_all("ol"):
        if ordered_list.find("span", class_="museum-type"):
            return ordered_list
        if ordered_list.find(attrs={"typeof": re.compile(r"^(Museum|ArtGallery)$")}):
            return ordered_list
    return None


def build_museum_list_item(soup: BeautifulSoup, row: ContentRow, language: str) -> Tag:
    li = soup.new_tag("li")
    li["property"] = "itemListElement"
    li["typeof"] = "ListItem"

    wrapper = soup.new_tag("span")
    wrapper["typeof"] = row.item_type

    name = soup.new_tag("span")
    name["property"] = "name"
    name.string = row.localized("name", language)
    wrapper.append(name)
    wrapper.append(soup.new_string("\n"))

    link = soup.new_tag("link")
    link["property"] = "sameAs"
    link["href"] = row.wikidata_url
    wrapper.append(link)

    li.append(wrapper)
    li.append(soup.new_string("\n"))

    type_label = soup.new_tag("span")
    type_label["class"] = "museum-type"
    type_label.string = row.localized("type_label", language, required=False) or row.item_type
    li.append(type_label)
    return li


def build_museum_card(soup: BeautifulSoup, row: ContentRow, language: str) -> Tag:
    article = soup.new_tag("article")
    article["class"] = "museum-card"

    icon = soup.new_tag("div")
    icon["class"] = "museum-icon"
    article.append(icon)
    article.append(soup.new_string("\n"))

    heading = soup.new_tag("h2")
    heading["class"] = "museum-name"
    heading["typeof"] = row.item_type

    name = soup.new_tag("span")
    name["property"] = "name"
    name.string = row.localized("name", language)
    heading.append(name)

    link = soup.new_tag("link")
    link["property"] = "sameAs"
    link["href"] = row.wikidata_url
    heading.append(soup.new_string("\n"))
    heading.append(link)

    article.append(heading)
    article.append(soup.new_string("\n"))

    type_label = soup.new_tag("span")
    type_label["class"] = "museum-type"
    type_label.string = row.localized("type_label", language, required=False) or row.item_type
    article.append(type_label)
    return article


def render_quote_grid(
    soup: BeautifulSoup,
    rows: list[ContentRow],
    language: str,
) -> tuple[int, int]:
    added = 0
    skipped = 0
    for row in rows:
        section = find_quote_section(soup, row, language)
        grid = section.find("div", class_="quotes-grid")
        if not isinstance(grid, Tag):
            raise ContentUpdateError(
                f"quotes:{row.row_number}: quotes-grid missing for category"
            )
        if has_existing_quote(grid, row, language):
            skipped += 1
            continue
        grid.append(soup.new_string("\n"))
        grid.append(build_quote_card(soup, row, language))
        grid.append(soup.new_string("\n"))
        added += 1
    return added, skipped


def find_quote_section(soup: BeautifulSoup, row: ContentRow, language: str) -> Tag:
    expected = quote_category_labels(row, language)
    for section in soup.find_all("section", class_="quote-section"):
        heading = section.find(["h2", "h3"], class_=re.compile(r"section-title"))
        if heading and heading.get_text(" ", strip=True) in expected:
            return section
    raise ContentUpdateError(
        f"quotes:{row.row_number}: category section not found for {language}: {sorted(expected)}"
    )


def build_quote_card(soup: BeautifulSoup, row: ContentRow, language: str) -> Tag:
    card = soup.new_tag("div")
    card["class"] = "quote-card"
    if row.local_qid:
        card["data-q315-source"] = f"local:{row.local_qid}"
        card["data-q315-function"] = f"local:{CONTENT_RENDER_FUNCTION}"

    quote = soup.new_tag("p")
    quote["class"] = "quote-text"
    part_qids = split_qids(row.data.get("part_qids", ""))
    if part_qids:
        quote["data-q315-parts"] = " ".join(f"local:{qid}" for qid in part_qids)
    quote.string = row.localized("quote", language)
    card.append(quote)
    card.append(soup.new_string("\n"))

    attribution = soup.new_tag("p")
    attribution["class"] = "quote-author"
    attribution_qid = row.data.get("attribution_qid", "").strip()
    if attribution_qid:
        attribution["data-q315-source"] = f"local:{attribution_qid}"
        attribution["data-q315-function"] = f"local:{CONTENT_RENDER_FUNCTION}"
    attribution.string = row.localized("attribution", language)
    card.append(attribution)
    return card


def has_existing_entry(container: Tag, row: ContentRow, language: str) -> bool:
    if row.wikidata_url and container.find("link", attrs={"href": row.wikidata_url}):
        return True
    expected_name = normalize_text(row.localized("name", language))
    for name_node in container.find_all(attrs={"property": "name"}):
        if normalize_text(name_node.get_text(" ", strip=True)) == expected_name:
            return True
    return False


def has_existing_quote(container: Tag, row: ContentRow, language: str) -> bool:
    expected_quote = normalize_text(row.localized("quote", language))
    expected_attribution = normalize_text(row.localized("attribution", language))
    for card in container.find_all("div", class_="quote-card"):
        quote = card.find("p", class_="quote-text")
        attribution = card.find("p", class_="quote-author")
        if not quote or not attribution:
            continue
        if (
            normalize_text(quote.get_text(" ", strip=True)) == expected_quote
            and normalize_text(attribution.get_text(" ", strip=True)) == expected_attribution
        ):
            return True
    return False


def sort_children_by_name(container: Tag) -> None:
    sortable = [
        child
        for child in container.find_all(recursive=False)
        if isinstance(child, Tag) and child.find(attrs={"property": "name"})
    ]
    if not sortable:
        return
    sortable.sort(key=lambda tag: normalize_text(tag.find(attrs={"property": "name"}).get_text(" ", strip=True)))
    container.clear()
    container.append("\n")
    for child in sortable:
        container.append(child)
        container.append("\n")


def normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFC", value).casefold()
    return unicodedata.normalize("NFC", " ".join(folded.split()))


def canonical_wikidata_url(wikidata_url: str) -> str:
    qid = wikidata_qid(wikidata_url)
    return f"https://www.wikidata.org/wiki/{qid}" if qid else wikidata_url.strip()


def wikidata_qid(wikidata_url: str) -> str:
    match = re.search(r"/(?:wiki|entity)/(Q[1-9][0-9]*)$", wikidata_url.strip())
    return match.group(1) if match else ""


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()[:80].strip("-")
    if slug:
        return slug
    # Names written entirely in a non-Latin script leave nothing behind after the
    # ASCII fold. Fall back to a digest so the row still gets a stable id instead
    # of failing validation.
    collapsed = normalize_text(value)
    if not collapsed:
        return ""
    return f"x-{hashlib.sha1(collapsed.encode('utf-8')).hexdigest()[:16]}"


def discover_csv_paths(input_dir: Path, selected: Iterable[str]) -> dict[str, Path]:
    return {
        family_name: input_dir / FAMILIES[family_name].csv_name
        for family_name in selected
    }


LOCAL_BINDING_RE = re.compile(r"local:(Q[1-9][0-9]*)")
QID_BINDING_RE = re.compile(r"data-(?:content|entity)=[\"']local:(Q[1-9][0-9]*)[\"']")
QID_COLUMNS = ("local_qid", "creator_qid", "attribution_qid", "simple_local_qid")
# The container each Q315 renderer writes entries into, so a binding elsewhere on
# the page (breadcrumbs, intro prose) is not mistaken for a content orphan.
Q315_CONTENT_CONTAINERS = {
    "ordered-list": ("ol", r"(book-list|media-list|music-list)"),
    "museum-grid": ("div", r"museums-grid"),
    "quote-grid": ("div", r"quotes-grid"),
}
# The entry element each renderer writes inside its container. Used by --mode bind
# to find an entry that is already on the page, never to create one.
Q315_ENTRY_PATTERNS = {
    "ordered-list": r"\s*<li\b[\s\S]*?</li>",
    "museum-grid": r"\s*<article\b[^>]*class=[\"'][^\"']*museum-card[^\"']*[\"'][\s\S]*?</article>",
    "quote-grid": r"\s*<div\b[^>]*class=[\"'][^\"']*quote-card[^\"']*[\"'][\s\S]*?</div>",
}


@dataclass(frozen=True)
class QidDiff:
    family: str
    path: Path
    missing: tuple[str, ...]
    orphaned: tuple[str, ...]
    checked: int

    @property
    def clean(self) -> bool:
        return not self.missing and not self.orphaned


def qid_number(qid: str) -> int:
    return int(qid[1:])


def csv_bound_qids(row: ContentRow) -> set[str]:
    """Every content-item QID a single CSV row claims to bind."""
    qids = set()
    for column in QID_COLUMNS:
        value = row.data.get(column, "").strip()
        if re.fullmatch(r"Q[1-9][0-9]*", value):
            qids.add(value)
    qids.update(split_qids(row.data.get("part_qids", "")))
    return qids


def derived_q315_qids(family: FamilyConfig, rows: list[ContentRow]) -> set[str]:
    """QIDs the Q315 renderer emits from a row without the CSV naming them.

    Museum type labels are chosen from the row's item type rather than stored in
    a column, so they are bound on the source with no CSV field to point at them.
    """
    if family.renderer == "museum-grid":
        return {museum_type_label_qid(row) for row in rows}
    return set()


def q315_content_containers(html_content: str, tag: str, class_pattern: str) -> list[str]:
    inners: list[str] = []
    for match in re.finditer(rf"<{tag}\b[^>]*>", html_content, re.IGNORECASE):
        if not re.search(
            rf"class=[\"'][^\"']*{class_pattern}[^\"']*[\"']",
            match.group(0),
            re.IGNORECASE,
        ):
            continue
        bounds = find_matching_close(html_content, tag, match.start(), match.end())
        if bounds:
            inners.append(html_content[bounds[1] : bounds[2]])
    return inners


def q315_content_qids(family: FamilyConfig, html_content: str) -> set[str]:
    """QIDs bound inside the family's content container on its Q315 source."""
    spec = Q315_CONTENT_CONTAINERS.get(family.renderer)
    if not spec:
        return set()
    qids: set[str] = set()
    for inner in q315_content_containers(html_content, *spec):
        qids.update(QID_BINDING_RE.findall(inner))
    return qids


def diff_q315_family(family: FamilyConfig, rows: list[ContentRow]) -> QidDiff:
    target = family.q315_target
    if not target:
        raise ContentUpdateError(f"{family.name}: Q315 source page is not configured")
    html_content = target.read_text(encoding="utf-8")

    expected: set[str] = set()
    for row in rows:
        expected |= csv_bound_qids(row)
    expected |= derived_q315_qids(family, rows)

    # A CSV binding counts as present anywhere in the document: composed
    # paragraphs and split quotes reference their parts outside the entry markup.
    document = set(LOCAL_BINDING_RE.findall(html_content))
    missing = tuple(sorted(expected - document, key=qid_number))

    orphaned: tuple[str, ...] = ()
    if family.mirrors_q315:
        orphaned = tuple(sorted(q315_content_qids(family, html_content) - expected, key=qid_number))

    return QidDiff(
        family=family.name,
        path=target,
        missing=missing,
        orphaned=orphaned,
        checked=len(expected),
    )


def format_qid_diffs(diffs: list[QidDiff]) -> str:
    if not diffs:
        return "No families compared."
    lines: list[str] = []
    for diff in diffs:
        header = (
            f"{diff.family}: {diff.checked} CSV binding(s); "
            f"missing={len(diff.missing)}, orphaned={len(diff.orphaned)}; "
            f"{to_repo_relative(diff.path)}"
        )
        lines.append(header)
        for qid in diff.missing:
            lines.append(f"  - missing:  {qid} is bound by the CSV but absent from the source")
        for qid in diff.orphaned:
            lines.append(f"  - orphaned: {qid} is bound on the source but has no CSV row")
    return "\n".join(lines)


def backfill_q315_qids(family: FamilyConfig, rows: list[ContentRow]) -> int:
    """Recover QID columns the CSV cannot otherwise express from the Q315 source.

    ``build_q315_list_item_html`` renders a book's author as a bound content item
    when ``creator_qid`` is set, but nothing ever wrote that column, so the
    bindings already on the abstract page were invisible to the CSV. Pair them
    back up by the name QID, which both sides share.
    """
    if family.name != "books":
        return 0
    target = family.q315_target
    if not target or not target.exists():
        return 0
    pairs = q315_creator_pairs(target.read_text(encoding="utf-8"))
    filled = 0
    for row in rows:
        if row.data.get("creator_qid", "").strip():
            continue
        creator_qid = pairs.get(row.local_qid, "")
        if creator_qid:
            row.data["creator_qid"] = creator_qid
            filled += 1
    return filled


def q315_creator_pairs(html_content: str) -> dict[str, str]:
    """Map each book's name QID to its author QID on the abstract source."""
    soup = BeautifulSoup(html_content, features="html.parser")
    pairs: dict[str, str] = {}
    for item in soup.find_all("li"):
        name_node = item.find(attrs={"property": "name"})
        creator_node = item.find("span", class_="book-author")
        if not isinstance(name_node, Tag) or not isinstance(creator_node, Tag):
            continue
        name_qid = content_qid_from_tag(name_node)
        creator_qid = content_qid_from_tag(creator_node)
        if name_qid and creator_qid:
            pairs[name_qid] = creator_qid
    return pairs


@dataclass
class BindResult:
    family: str
    path: Path
    language: str
    bound: int
    already: int
    unmatched: list[str]
    changed: bool


def container_spans(html_content: str, tag: str, class_pattern: str) -> list[tuple[int, int]]:
    """Inner bounds of every container the renderer writes entries into."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(rf"<{tag}\b[^>]*>", html_content, re.IGNORECASE):
        if not re.search(
            rf"class=[\"'][^\"']*{class_pattern}[^\"']*[\"']", match.group(0), re.IGNORECASE
        ):
            continue
        bounds = find_matching_close(html_content, tag, match.start(), match.end())
        if bounds:
            spans.append((bounds[1], bounds[2]))
    return spans


def bind_page(
    html_content: str,
    family: FamilyConfig,
    rows: list[ContentRow],
    language: str,
) -> tuple[str, int, int, list[str]]:
    """Add binding metadata to entries that are already on the page.

    This is the safe complement of the retired apply path: it only ever adds
    ``data-q315-source``/``data-q315-function`` to an entry that already matches
    a CSV row, and never inserts, reorders, removes or rewrites content. A row
    with no matching entry is reported, not created.
    """
    tag, class_pattern = Q315_CONTENT_CONTAINERS[family.renderer]
    entry_pattern = Q315_ENTRY_PATTERNS[family.renderer]
    bound = already = 0
    matched: set[int] = set()

    # Right to left, so an edit never invalidates a span not yet visited.
    for open_end, close_start in reversed(container_spans(html_content, tag, class_pattern)):
        inner = html_content[open_end:close_start]
        for row in rows:
            if not row.local_qid:
                continue
            match = matching_block(extract_blocks(inner, entry_pattern), row, language)
            if not match:
                continue
            matched.add(row.row_number)
            start, end, block = match
            updated_block = add_q315_binding(block, row)
            if updated_block != block:
                inner = inner[:start] + updated_block + inner[end:]
                bound += 1
            else:
                already += 1
        html_content = html_content[:open_end] + inner + html_content[close_start:]

    unmatched = [row.stable_id for row in rows if row.local_qid and row.row_number not in matched]
    return html_content, bound, already, unmatched


def bind_family(family: FamilyConfig, rows: list[ContentRow], *, apply: bool) -> list[BindResult]:
    if family.renderer not in Q315_CONTENT_CONTAINERS:
        raise ContentUpdateError(
            f"{family.name}: --mode bind does not support the {family.renderer} renderer"
        )
    results: list[BindResult] = []
    for target in family.targets():
        original = target.path.read_text(encoding="utf-8")
        updated, bound, already, unmatched = bind_page(original, family, rows, target.language)
        changed = updated != original
        if apply and changed:
            rewrite_text_file(target.path, lambda _content, updated=updated: updated)
        results.append(
            BindResult(
                family=family.name,
                path=target.path,
                language=target.language,
                bound=bound,
                already=already,
                unmatched=unmatched,
                changed=changed,
            )
        )
    return results


def format_bind_results(results: list[BindResult]) -> str:
    if not results:
        return "No pages bound."
    lines = []
    for result in results:
        lines.append(
            f"{result.family}:{result.language}: "
            f"{'changed' if result.changed else 'unchanged'}; "
            f"bound={result.bound}, already={result.already}, "
            f"unmatched={len(result.unmatched)}; {to_repo_relative(result.path)}"
        )
        for stable_id in result.unmatched[:5]:
            lines.append(f"  - no entry on the page for {stable_id}")
    return "\n".join(lines)


def format_changes(changes: list[PageChange]) -> str:
    if not changes:
        return "No target pages checked."
    lines = []
    for change in changes:
        action = "changed" if change.changed else "unchanged"
        lines.append(
            f"{change.family}:{change.language}: {action}; "
            f"added={change.added}, skipped={change.skipped}, repaired={change.repaired}; "
            f"{to_repo_relative(change.path)}"
        )
    return "\n".join(lines)


@dataclass
class WikibaseRowAction:
    family: str
    row_number: int
    name: str
    wikidata_qid: str
    local_qid: str
    action: str
    local_field: str = "local_qid"


@dataclass
class ContentItemIndex:
    by_wikidata: dict[str, list[str]]
    by_text: dict[str, list[str]]

    def lookup_wikidata(self, qid: str) -> list[str]:
        return self.by_wikidata.get(qid, [])

    def lookup_text(self, text: str) -> list[str]:
        return self.by_text.get(normalize_text(text), [])


def wikibase_plan_family(
    family: FamilyConfig,
    rows: list[ContentRow],
    client: WikibaseClient,
    *,
    allow_create: bool = False,
    index: ContentItemIndex | None = None,
) -> list[WikibaseRowAction]:
    if family.name == "cv":
        return wikibase_plan_cv_family(rows, client, allow_create=allow_create, index=index)
    actions: list[WikibaseRowAction] = []
    for row in rows:
        name = content_text_for_wikibase(row)
        wikidata = wikidata_qid(row.wikidata_url)
        if row.local_qid:
            if wikibase_content_item_missing_claims(client, row.local_qid, row):
                actions.append(
                    WikibaseRowAction(family.name, row.row_number, name, wikidata, row.local_qid, "repair")
                )
                continue
            actions.append(
                WikibaseRowAction(family.name, row.row_number, name, wikidata, row.local_qid, "skip-local-qid")
            )
            continue
        local_qid, lookup_status = find_existing_local_content_item(client, row, index=index)
        if local_qid:
            actions.append(
                WikibaseRowAction(family.name, row.row_number, name, wikidata, local_qid, "bind-existing")
            )
        elif lookup_status == "ambiguous":
            actions.append(
                WikibaseRowAction(family.name, row.row_number, name, wikidata, "", "ambiguous-existing-items")
            )
        else:
            actions.append(
                WikibaseRowAction(
                    family.name,
                    row.row_number,
                    name,
                    wikidata,
                    "",
                    "create" if allow_create else "missing-existing-item",
                )
            )
    return actions


def wikibase_plan_cv_family(
    rows: list[ContentRow],
    client: WikibaseClient,
    *,
    allow_create: bool = False,
    index: ContentItemIndex | None = None,
) -> list[WikibaseRowAction]:
    actions: list[WikibaseRowAction] = []
    for row in rows:
        for variant, local_field, variant_row in cv_wikibase_variants(row):
            action = wikibase_plan_single_row(
                FAMILIES["cv"],
                variant_row,
                client,
                allow_create=allow_create,
                index=index,
            )
            action.family = f"cv-{variant}"
            action.local_field = local_field
            actions.append(action)
    return actions


def wikibase_plan_single_row(
    family: FamilyConfig,
    row: ContentRow,
    client: WikibaseClient,
    *,
    allow_create: bool = False,
    index: ContentItemIndex | None = None,
) -> WikibaseRowAction:
    name = content_text_for_wikibase(row)
    wikidata = wikidata_qid(row.wikidata_url)
    if row.local_qid:
        if wikibase_content_item_missing_claims(client, row.local_qid, row):
            return WikibaseRowAction(family.name, row.row_number, name, wikidata, row.local_qid, "repair")
        return WikibaseRowAction(family.name, row.row_number, name, wikidata, row.local_qid, "skip-local-qid")
    local_qid, lookup_status = find_existing_local_content_item(client, row, index=index)
    if local_qid:
        return WikibaseRowAction(family.name, row.row_number, name, wikidata, local_qid, "bind-existing")
    if lookup_status == "ambiguous":
        return WikibaseRowAction(family.name, row.row_number, name, wikidata, "", "ambiguous-existing-items")
    return WikibaseRowAction(
        family.name,
        row.row_number,
        name,
        wikidata,
        "",
        "create" if allow_create else "missing-existing-item",
    )


def wikibase_apply_family(
    family: FamilyConfig,
    rows: list[ContentRow],
    client: WikibaseClient,
    *,
    summary: str,
    allow_create: bool = False,
    index: ContentItemIndex | None = None,
) -> list[WikibaseRowAction]:
    if family.name == "cv":
        return wikibase_apply_cv_family(rows, client, summary=summary, allow_create=allow_create, index=index)
    index = index or build_content_item_index(client)
    planned = wikibase_plan_family(family, rows, client, allow_create=allow_create, index=index)
    completed: list[WikibaseRowAction] = []
    rows_by_number = {row.row_number: row for row in rows}
    for action in planned:
        row = rows_by_number[action.row_number]
        if action.action == "create":
            if not allow_create:
                completed.append(
                    WikibaseRowAction(
                        action.family,
                        action.row_number,
                        action.name,
                        action.wikidata_qid,
                        "",
                        "missing-existing-item",
                    )
                )
                continue
            local_qid = create_local_item_for_row(client, family, row, summary=summary)
            row.data["local_qid"] = local_qid
            completed.append(
                WikibaseRowAction(
                    action.family,
                    action.row_number,
                    action.name,
                    action.wikidata_qid,
                    local_qid,
                    "created",
                )
            )
        elif action.action == "repair":
            repair_local_item_for_row(client, family, row, summary=summary)
            completed.append(
                WikibaseRowAction(
                    action.family,
                    action.row_number,
                    action.name,
                    action.wikidata_qid,
                    action.local_qid,
                    "repaired",
                )
            )
        elif action.action == "bind-existing":
            row.data["local_qid"] = action.local_qid
            if wikibase_content_item_missing_claims(client, action.local_qid, row):
                row.data["local_qid"] = action.local_qid
                repair_local_item_for_row(client, family, row, summary=summary)
                completed.append(
                    WikibaseRowAction(
                        action.family,
                        action.row_number,
                        action.name,
                        action.wikidata_qid,
                        action.local_qid,
                        "bound-existing-repaired",
                    )
                )
                continue
            completed.append(
                WikibaseRowAction(
                    action.family,
                    action.row_number,
                    action.name,
                    action.wikidata_qid,
                    action.local_qid,
                    "bound-existing",
                )
            )
        else:
            completed.append(action)
    return completed


def wikibase_apply_cv_family(
    rows: list[ContentRow],
    client: WikibaseClient,
    *,
    summary: str,
    allow_create: bool = False,
    index: ContentItemIndex | None = None,
) -> list[WikibaseRowAction]:
    index = index or build_content_item_index(client)
    completed: list[WikibaseRowAction] = []
    rows_by_number = {row.row_number: row for row in rows}
    for row in rows:
        for variant, local_field, variant_row in cv_wikibase_variants(row):
            action = wikibase_plan_single_row(
                FAMILIES["cv"],
                variant_row,
                client,
                allow_create=allow_create,
                index=index,
            )
            action.family = f"cv-{variant}"
            action.local_field = local_field
            original_row = rows_by_number[action.row_number]
            if action.action == "create":
                if not allow_create:
                    action.action = "missing-existing-item"
                    completed.append(action)
                    continue
                local_qid = create_local_item_for_row(client, FAMILIES["cv"], variant_row, summary=summary)
                original_row.data[local_field] = local_qid
                completed.append(
                    WikibaseRowAction(
                        action.family,
                        action.row_number,
                        action.name,
                        action.wikidata_qid,
                        local_qid,
                        "created",
                        local_field,
                    )
                )
            elif action.action == "repair":
                repair_local_item_for_row(client, FAMILIES["cv"], variant_row, summary=summary)
                completed.append(action)
            elif action.action == "bind-existing":
                original_row.data[local_field] = action.local_qid
                variant_row.data["local_qid"] = action.local_qid
                if wikibase_content_item_missing_claims(client, action.local_qid, variant_row):
                    repair_local_item_for_row(client, FAMILIES["cv"], variant_row, summary=summary)
                    action.action = "bound-existing-repaired"
                else:
                    action.action = "bound-existing"
                completed.append(action)
            else:
                completed.append(action)
    return completed


def cv_wikibase_variants(row: ContentRow) -> list[tuple[str, str, ContentRow]]:
    variants: list[tuple[str, str, ContentRow]] = []
    targets = cv_targets(row)
    if "detailed" in targets:
        variants.append(("detailed", "local_qid", row))
    if "simple" in targets:
        data = dict(row.data)
        data["content"] = cv_simple_content(row, "en")
        for language in LANGUAGES:
            value = row.data.get(f"simple_content_{language}", "").strip()
            if value:
                data[f"content_{language}"] = value
        data["local_qid"] = row.data.get("simple_local_qid", "").strip()
        variants.append(("simple", "simple_local_qid", ContentRow(row.family, row.row_number, data)))
    return variants


def wikibase_content_item_missing_claims(
    client: WikibaseClient,
    local_qid: str,
    row: ContentRow,
) -> bool:
    entity = client.entities([local_qid]).get(local_qid, {})
    if entity.get("missing"):
        return True
    if row.family in {"quotes", "cv"} and split_qids(row.data.get("part_qids", "")):
        return False
    claims = entity.get("claims", {})
    if not has_item_claim(claims, INSTANCE_OF_PROPERTY, ABSTRACT_CONTENT_ITEM):
        return True
    existing_languages = monolingual_claim_languages(claims, MONOLINGUAL_CONTENT_PROPERTY)
    return any(language not in existing_languages for language in LANGUAGES)


def has_item_claim(claims: dict, property_id: str, item_id: str) -> bool:
    for claim in claims.get(property_id, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("id") == item_id:
            return True
    return False


def monolingual_claim_languages(claims: dict, property_id: str) -> set[str]:
    languages: set[str] = set()
    for claim in claims.get(property_id, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        language = value.get("language")
        if language:
            languages.add(language)
    return languages


def content_text_for_wikibase(row: ContentRow) -> str:
    if row.family == "quotes":
        return row.localized("quote", "en")
    if row.family == "cv":
        return cv_content(row, "en")
    return row.localized("name", "en", required=True)


def content_texts_for_wikibase(row: ContentRow) -> dict[str, str]:
    if row.family == "cv":
        return {language: cv_content(row, language) for language in LANGUAGES}
    field = "quote" if row.family == "quotes" else "name"
    values = {
        language: row.localized(field, language, required=False)
        for language in LANGUAGES
    }
    fallback = content_text_for_wikibase(row)
    return {language: value or fallback for language, value in values.items()}


def find_existing_local_content_item(
    client: WikibaseClient,
    row: ContentRow,
    *,
    index: ContentItemIndex | None = None,
) -> tuple[str, str]:
    wikidata = wikidata_qid(row.wikidata_url)
    if wikidata:
        matches = index.lookup_wikidata(wikidata) if index else maybe_one(find_local_item_by_wikidata_qid(client, wikidata))
        if len(matches) == 1:
            return matches[0], "found"
        if len(matches) > 1:
            return "", "ambiguous"

    text = content_text_for_wikibase(row)
    matches = index.lookup_text(text) if index else find_local_items_by_p40(client, text)
    if len(matches) == 1:
        return matches[0], "found"
    if len(matches) > 1:
        return "", "ambiguous"
    if index:
        return "", "missing"

    matches = find_local_content_items_by_label(client, text)
    if len(matches) == 1:
        return matches[0], "found"
    if len(matches) > 1:
        return "", "ambiguous"
    return "", "missing"


def maybe_one(value: str) -> list[str]:
    return [value] if value else []


def build_content_item_index(client: WikibaseClient) -> ContentItemIndex:
    base_url = client.api.removesuffix("/w/api.php")
    query = (
        "SELECT ?item ?label ?wikidata ?content WHERE { "
        f"?item <{base_url}/prop/direct/P8> <{base_url}/entity/{ABSTRACT_CONTENT_ITEM}> . "
        "OPTIONAL { ?item <http://www.w3.org/2000/01/rdf-schema#label> ?label . "
        'FILTER(LANG(?label) = "en") } '
        f"OPTIONAL {{ ?item <{base_url}/prop/direct/P4> ?wikidata . }} "
        f"OPTIONAL {{ ?item <{base_url}/prop/direct/P40> ?content . }} "
        "}"
    )
    by_wikidata: dict[str, set[str]] = {}
    by_text: dict[str, set[str]] = {}
    for binding in sparql_query(client, query).get("results", {}).get("bindings", []):
        item = binding.get("item", {}).get("value", "").rstrip("/").split("/")[-1]
        if not re.fullmatch(r"Q[1-9][0-9]*", item):
            continue
        wikidata = binding.get("wikidata", {}).get("value", "")
        if wikidata:
            by_wikidata.setdefault(wikidata, set()).add(item)
        for key in ("content", "label"):
            text = binding.get(key, {}).get("value", "")
            if text:
                by_text.setdefault(normalize_text(text), set()).add(item)
    return ContentItemIndex(
        by_wikidata={key: sorted(value) for key, value in by_wikidata.items()},
        by_text={key: sorted(value) for key, value in by_text.items()},
    )


def find_local_item_by_wikidata_qid(client: WikibaseClient, qid: str) -> str:
    base_url = client.api.removesuffix("/w/api.php")
    query = (
        "SELECT ?item WHERE { "
        f'?item <{base_url}/prop/direct/P4> "{qid}" . '
        "} LIMIT 1"
    )
    payload = sparql_query(client, query)
    bindings = payload.get("results", {}).get("bindings", [])
    if not bindings:
        return ""
    value = bindings[0].get("item", {}).get("value", "")
    return value.rstrip("/").split("/")[-1]


def find_local_items_by_p40(client: WikibaseClient, text: str) -> list[str]:
    base_url = client.api.removesuffix("/w/api.php")
    query = (
        "SELECT DISTINCT ?item WHERE { "
        f"?item <{base_url}/prop/direct/P8> <{base_url}/entity/{ABSTRACT_CONTENT_ITEM}> . "
        f'?item <{base_url}/prop/direct/P40> ?content . '
        f'FILTER(STR(?content) = "{sparql_string(text)}") '
        "} LIMIT 5"
    )
    return qids_from_sparql(sparql_query(client, query))


def find_local_content_items_by_label(client: WikibaseClient, text: str) -> list[str]:
    payload = client.request(
        {
            "action": "wbsearchentities",
            "language": "en",
            "type": "item",
            "limit": 10,
            "search": text,
        }
    )
    candidates = [result["id"] for result in payload.get("search", []) if result.get("label") == text]
    if not candidates:
        return []
    entities = client.entities(candidates)
    return [
        qid
        for qid in candidates
        if has_item_claim(entities.get(qid, {}).get("claims", {}), INSTANCE_OF_PROPERTY, ABSTRACT_CONTENT_ITEM)
    ]


def qids_from_sparql(payload: dict) -> list[str]:
    qids: list[str] = []
    for binding in payload.get("results", {}).get("bindings", []):
        value = binding.get("item", {}).get("value", "")
        qid = value.rstrip("/").split("/")[-1]
        if re.fullmatch(r"Q[1-9][0-9]*", qid):
            qids.append(qid)
    return qids


def sparql_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def sparql_query(client: WikibaseClient, query: str) -> dict:
    from urllib.parse import urlencode
    from urllib.request import Request

    endpoint = client.api.replace("/w/api.php", "/query/sparql")
    encoded = urlencode({"format": "json", "query": query}).encode()
    request = Request(endpoint, data=encoded, headers={"User-Agent": "johnsamuelwrites-content-update/1.0"})
    with client.opener.open(request, timeout=client.timeout) as response:
        return json.load(response)


def create_local_item_for_row(
    client: WikibaseClient,
    family: FamilyConfig,
    row: ContentRow,
    *,
    summary: str,
) -> str:
    name = content_text_for_wikibase(row)
    wikidata = wikidata_qid(row.wikidata_url)
    if family.wikidata_required and not wikidata:
        raise ContentUpdateError(f"{family.name}:{row.row_number}: Wikidata QID required for Wikibase create")
    data = build_wikibase_content_item_data(name, wikidata, content_texts_for_wikibase(row))
    result = client.edit_entity(data, summary=summary)
    entity_id = result.get("entity", {}).get("id")
    if not entity_id:
        raise WikibaseError(f"creation did not return entity id: {result}")
    return entity_id


def repair_local_item_for_row(
    client: WikibaseClient,
    family: FamilyConfig,
    row: ContentRow,
    *,
    summary: str,
) -> None:
    name = content_text_for_wikibase(row)
    wikidata = wikidata_qid(row.wikidata_url)
    entity = client.entities([row.local_qid]).get(row.local_qid, {})
    data = build_wikibase_repair_data(name, wikidata, entity.get("claims", {}), content_texts_for_wikibase(row))
    client.edit_entity(data, entity_id=row.local_qid, summary=summary)


def build_wikibase_content_item_data(
    name: str,
    wikidata: str = "",
    content_by_language: dict[str, str] | None = None,
) -> dict:
    label = wikibase_label_text(name)
    content_by_language = content_by_language or {language: name for language in LANGUAGES}
    data = {
        "labels": {
            language: {"language": language, "value": label}
            for language in LANGUAGES
        },
        "descriptions": {
            "en": {
                "language": "en",
                "value": "language-independent content component used by an abstract page",
            }
        },
        "claims": {
            INSTANCE_OF_PROPERTY: [
                statement(
                    INSTANCE_OF_PROPERTY,
                    "wikibase-item",
                    datavalue(ABSTRACT_CONTENT_ITEM, "wikibase-item"),
                )
            ],
            MONOLINGUAL_CONTENT_PROPERTY: [
                statement(
                    MONOLINGUAL_CONTENT_PROPERTY,
                    "monolingualtext",
                    datavalue(f'{language}:"{content_by_language[language]}"', "monolingualtext"),
                )
                for language in LANGUAGES
            ],
        },
    }
    if wikidata:
        data["claims"][WIKIDATA_ITEM_PROPERTY] = [
            statement(
                WIKIDATA_ITEM_PROPERTY,
                "external-id",
                datavalue(wikidata, "external-id"),
            )
        ]
    return data


def build_wikibase_repair_data(
    name: str,
    wikidata: str,
    claims: dict,
    content_by_language: dict[str, str] | None = None,
) -> dict:
    label = wikibase_label_text(name)
    content_by_language = content_by_language or {language: name for language in LANGUAGES}
    data = {
        "labels": {
            language: {"language": language, "value": label}
            for language in LANGUAGES
        },
        "descriptions": {
            "en": {
                "language": "en",
                "value": "language-independent content component used by an abstract page",
            }
        },
        "claims": {},
    }
    if not has_item_claim(claims, INSTANCE_OF_PROPERTY, ABSTRACT_CONTENT_ITEM):
        data["claims"][INSTANCE_OF_PROPERTY] = [
            statement(
                INSTANCE_OF_PROPERTY,
                "wikibase-item",
                datavalue(ABSTRACT_CONTENT_ITEM, "wikibase-item"),
            )
        ]
    existing_languages = monolingual_claim_languages(claims, MONOLINGUAL_CONTENT_PROPERTY)
    missing_content = [
        statement(
            MONOLINGUAL_CONTENT_PROPERTY,
            "monolingualtext",
            datavalue(f'{language}:"{content_by_language[language]}"', "monolingualtext"),
        )
        for language in LANGUAGES
        if language not in existing_languages
    ]
    if missing_content:
        data["claims"][MONOLINGUAL_CONTENT_PROPERTY] = missing_content
    if wikidata and not has_string_claim(claims, WIKIDATA_ITEM_PROPERTY, wikidata):
        data["claims"][WIKIDATA_ITEM_PROPERTY] = [
            statement(
                WIKIDATA_ITEM_PROPERTY,
                "external-id",
                datavalue(wikidata, "external-id"),
            )
        ]
    return {key: value for key, value in data.items() if key != "claims" or value}


def wikibase_label_text(value: str) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= 250:
        return collapsed
    return collapsed[:247].rstrip() + "..."


def has_string_claim(claims: dict, property_id: str, expected: str) -> bool:
    for claim in claims.get(property_id, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if value == expected:
            return True
    return False


def statement(property_id: str, datatype: str, value: dict) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": property_id,
            "datatype": datatype,
            "datavalue": value,
        },
        "type": "statement",
        "rank": "normal",
    }


def format_wikibase_actions(actions: list[WikibaseRowAction]) -> str:
    if not actions:
        return "No Wikibase rows checked."
    return "\n".join(
        f"{action.family}:{action.row_number}: {action.action}; "
        f"name={action.name}; wikidata={action.wikidata_qid or '-'}; "
        f"{action.local_field}={action.local_qid or '-'}"
        for action in actions
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        default="data/content-updates",
        help="Directory containing family CSV files.",
    )
    parser.add_argument(
        "--family",
        action="append",
        choices=sorted(FAMILIES),
        help="Family to process. May be repeated. Defaults to all families.",
    )
    parser.add_argument(
        "--mode",
        choices=(
            "validate",
            "check",
            "diff",
            "bind",
            "preview",
            "apply",
            "q315-preview",
            "q315-apply",
            "extract",
            "wikibase-plan",
            "wikibase-apply",
        ),
        default="preview",
        help=(
            "validate checks CSV and targets; check additionally asserts every Q315 "
            "source is already in sync with its CSV and exits non-zero otherwise; "
            "preview computes rendered page changes; "
            "apply rewrites rendered pages; q315-preview computes abstract source changes "
            "q315-apply rewrites abstract source pages; "
            "diff reports QID bindings present on one side only; "
            "bind adds binding metadata to entries already on the rendered pages "
            "without inserting or rewriting any content; "
            "extract backfills CSV rows and QID columns from existing pages; "
            "wikibase-plan checks local Wikibase; wikibase-apply binds/repairs local "
            "Wikibase items and writes local_qid."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Credential file for wikibase-apply.",
    )
    parser.add_argument("--api", default=None, help="Wikibase API endpoint.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="For --mode bind: write the binding metadata. Default is a dry run.",
    )
    parser.add_argument("--summary", default="Import curated content item")
    parser.add_argument(
        "--allow-create",
        action="store_true",
        help="Allow wikibase-apply to create missing local items. Default is bind/repair only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    selected = args.family or sorted(FAMILIES)
    csv_paths = discover_csv_paths(REPO_ROOT / args.input_dir, selected)

    try:
        all_changes: list[PageChange] = []
        all_diffs: list[QidDiff] = []
        all_binds: list[BindResult] = []
        all_wikibase_actions: list[WikibaseRowAction] = []
        extract_reports: list[str] = []
        client: WikibaseClient | None = None
        content_index: ContentItemIndex | None = None
        if args.mode in {"wikibase-plan", "wikibase-apply"}:
            load_env(args.env_file)
            api = args.api or os.getenv("WIKIBASE_API", DEFAULT_API)
            client = WikibaseClient(api, pause=0.25 if args.mode == "wikibase-apply" else 0)
            content_index = build_content_item_index(client)
            if args.mode == "wikibase-apply":
                username = os.getenv("WIKIBASE_USERNAME")
                password = os.getenv("WIKIBASE_PASSWORD")
                if not username or not password:
                    raise ContentUpdateError("WIKIBASE_USERNAME and WIKIBASE_PASSWORD are required")
                client.login(username, password)

        for family_name in selected:
            family = FAMILIES[family_name]
            if args.mode == "extract":
                extracted, added, backfilled = merge_extracted_rows(family, csv_paths[family_name])
                extract_reports.append(
                    f"{family.name}: extracted={extracted}, added={added}, "
                    f"backfilled={backfilled}; "
                    f"{to_repo_relative(csv_paths[family_name])}"
                )
                continue
            if args.mode in {"wikibase-plan", "wikibase-apply"}:
                fieldnames, rows = read_rows_with_header(family, csv_paths[family_name])
                assert client is not None
                if args.mode == "wikibase-plan":
                    assert content_index is not None
                    all_wikibase_actions.extend(
                        wikibase_plan_family(
                            family,
                            rows,
                            client,
                            allow_create=args.allow_create,
                            index=content_index,
                        )
                    )
                else:
                    all_wikibase_actions.extend(
                        wikibase_apply_family(
                            family,
                            rows,
                            client,
                        summary=args.summary,
                        allow_create=args.allow_create,
                        index=content_index,
                    )
                    )
                    write_rows(csv_paths[family_name], fieldnames, rows)
            else:
                rows = read_rows(family, csv_paths[family_name])
            if args.mode in {"q315-preview", "q315-apply"}:
                all_changes.extend(render_q315_family(family, rows, apply=args.mode == "q315-apply"))
            elif args.mode == "check":
                if family.q315_path:
                    all_changes.extend(render_q315_family(family, rows, apply=False))
            elif args.mode == "diff":
                if family.q315_path:
                    all_diffs.append(diff_q315_family(family, rows))
            elif args.mode == "bind":
                if family.renderer in Q315_CONTENT_CONTAINERS:
                    all_binds.extend(bind_family(family, rows, apply=args.apply))
            elif args.mode not in {"validate", "wikibase-plan", "wikibase-apply"}:
                all_changes.extend(render_family(family, rows, apply=args.mode == "apply"))
        if args.mode == "validate":
            print("Validation passed.")
        elif args.mode == "check":
            drifted = [change for change in all_changes if change.changed]
            print(format_changes(all_changes))
            if drifted:
                print(
                    "\nCheck failed: "
                    f"{len(drifted)} Q315 source(s) are out of sync with their CSV. "
                    "Run --mode q315-apply, then src/main/abstract/render_page.py.",
                    file=sys.stderr,
                )
                return 1
            print("\nCheck passed: every Q315 source is in sync with its CSV.")
        elif args.mode == "bind":
            print(format_bind_results(all_binds))
            if not args.apply:
                print("\nDry run only; pass --apply to write.")
        elif args.mode == "diff":
            print(format_qid_diffs(all_diffs))
            drifted = [diff for diff in all_diffs if not diff.clean]
            if drifted:
                print(
                    f"\n{len(drifted)} family/families have bindings on one side only.",
                    file=sys.stderr,
                )
                return 1
            print("\nNo binding drift: every CSV QID is on its source, and vice versa.")
        elif args.mode == "extract":
            print("\n".join(extract_reports))
        elif args.mode in {"wikibase-plan", "wikibase-apply"}:
            print(format_wikibase_actions(all_wikibase_actions))
        else:
            print(format_changes(all_changes))
        return 0
    except ContentUpdateError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
