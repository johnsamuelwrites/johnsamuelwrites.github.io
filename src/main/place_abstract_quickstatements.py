#!/usr/bin/env python3
"""Generate abstract Wikibase items for country and city path components."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import unquote, urlsplit

from abstract_quickstatements import (
    DESCRIPTIONS,
    LANGUAGES,
    LOCALIZED_PATH_SEGMENT,
    LOCALIZED_RELATIVE_PATH_OVERRIDE,
    PageParser,
    clean_title,
    parse_page,
    quickstatements_quote,
    resolve_link,
)
from paths import REPO_ROOT


COUNTRY_CLASS = "Q3065"
CITY_CLASS = "Q3066"
TRAVEL_ROOT = "Q3062"
COUNTRIES_COLLECTION = "Q3026"
CITIES_COLLECTION = "Q3025"

COUNTRY_DESCRIPTION = {
    **DESCRIPTIONS,
    "en": "language-independent country travel page",
    "fr": "page de voyage par pays indépendante de la langue",
    "es": "página de viaje por país independiente del idioma",
    "it": "pagina di viaggio per paese indipendente dalla lingua",
    "pt": "página de viagem por país independente do idioma",
}
CITY_DESCRIPTION = {
    **DESCRIPTIONS,
    "en": "language-independent city travel page",
    "fr": "page de voyage par ville indépendante de la langue",
    "es": "página de viaje por ciudad independiente del idioma",
    "it": "pagina di viaggio per città indipendente dalla lingua",
    "pt": "página de viagem por cidade independente do idioma",
}


def linked_group(source: Path) -> dict[str, Path]:
    parsed: PageParser = parse_page(source)
    group = {
        language: resolve_link(source, href)
        for language, href in parsed.links.items()
        if resolve_link(source, href).is_file()
    }
    group["en"] = source.resolve()
    return group


def country_groups() -> list[dict[str, Path]]:
    root = REPO_ROOT / "en/photography/countries"
    return [linked_group(path) for path in sorted(root.glob("*.html"))]


def city_groups() -> list[dict[str, Path]]:
    root = REPO_ROOT / "en/photography/cities"
    return [
        linked_group(path)
        for path in sorted(root.glob("*/*.html"), key=lambda value: value.as_posix())
    ]


def render(
    group: dict[str, Path],
    descriptions: dict[str, str],
    collection: str,
    item_class: str,
) -> str:
    statements = ["CREATE"]
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            title = clean_title(parse_page(path).title, language)
            statements.append(f'LAST|L{language}|"{quickstatements_quote(title)}"')
    for language in LANGUAGES:
        statements.append(
            f'LAST|D{language}|"{quickstatements_quote(descriptions[language])}"'
        )
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            statements.append(
                f'LAST|{LOCALIZED_PATH_SEGMENT}|'
                f'{language}:"{quickstatements_quote(path.stem)}"'
            )
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            relative = path.relative_to(REPO_ROOT / language).as_posix()
            statements.append(
                f'LAST|{LOCALIZED_RELATIVE_PATH_OVERRIDE}|'
                f'{language}:"{quickstatements_quote(relative)}"'
            )
    statements.extend((f"LAST|P8|{item_class}", f"LAST|P21|{collection}"))
    return "\n".join(statements)


def write_batch(
    groups: list[dict[str, Path]],
    descriptions: dict[str, str],
    collection: str,
    item_class: str,
    output: Path,
) -> None:
    output.write_text(
        "\n\n".join(
            render(group, descriptions, collection, item_class) for group in groups
        )
        + "\n",
        encoding="utf-8",
    )


def read_assigned_items(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [
            (
                row["item"].rstrip("/").split("/")[-1],
                row["label"].strip(),
            )
            for row in csv.DictReader(source)
        ]


def bind_items(
    groups: list[dict[str, Path]],
    assigned: list[tuple[str, str]],
    output: Path,
) -> dict[str, str]:
    if len(groups) != len(assigned):
        raise ValueError(
            f"{output}: {len(groups)} groups but {len(assigned)} assigned items"
        )
    english_paths: dict[str, str] = {}
    with output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("abstract_item", "language", "path", "path_segment"))
        for group, (item, expected_label) in zip(groups, assigned):
            english = group["en"]
            actual_label = clean_title(parse_page(english).title, "en")
            if actual_label != expected_label:
                raise ValueError(
                    f"{item}: expected {expected_label!r}, found {actual_label!r}"
                )
            english_paths[english.stem] = item
            for language in LANGUAGES:
                path = group[language]
                writer.writerow(
                    (
                        item,
                        language,
                        path.relative_to(REPO_ROOT).as_posix(),
                        path.stem,
                    )
                )
    return english_paths


def page_item_map(path: Path) -> dict[str, str]:
    mapped: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            relative = unquote(urlsplit(row.get("url", "")).path).lstrip("/")
            item = row.get("item", "").rstrip("/").split("/")[-1]
            if relative and item:
                mapped[relative] = item
    return mapped


def write_bound_statements(
    countries: list[dict[str, Path]],
    country_items: list[tuple[str, str]],
    cities: list[dict[str, Path]],
    city_items: list[tuple[str, str]],
) -> None:
    concrete_items = page_item_map(REPO_ROOT / "pages.csv")
    page_links: list[str] = []
    city_hierarchy: list[str] = []
    country_by_english_segment = {
        group["en"].stem: item
        for group, (item, _label) in zip(countries, country_items)
    }
    for groups, assigned in ((countries, country_items), (cities, city_items)):
        for group, (abstract_item, _label) in zip(groups, assigned):
            for path in group.values():
                relative = path.relative_to(REPO_ROOT).as_posix()
                concrete_item = concrete_items.get(relative)
                if not concrete_item:
                    raise ValueError(f"No concrete page item for {relative}")
                page_links.append(f"{concrete_item}|P12|{abstract_item}")
    for group, (city_item, _label) in zip(cities, city_items):
        country_segment = group["en"].parent.name
        country_item = country_by_english_segment[country_segment]
        city_hierarchy.append(f"{city_item}|P21|{country_item}")
    (REPO_ROOT / "quickstatements-link-place-pages-to-abstract.txt").write_text(
        "\n".join(sorted(page_links)) + "\n",
        encoding="utf-8",
    )
    (REPO_ROOT / "quickstatements-city-country-hierarchy.txt").write_text(
        "\n".join(city_hierarchy) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    countries = country_groups()
    cities = city_groups()
    write_batch(
        countries,
        COUNTRY_DESCRIPTION,
        COUNTRIES_COLLECTION,
        COUNTRY_CLASS,
        REPO_ROOT / "quickstatements-abstract-countries.txt",
    )
    write_batch(
        cities,
        CITY_DESCRIPTION,
        CITIES_COLLECTION,
        CITY_CLASS,
        REPO_ROOT / "quickstatements-abstract-cities.txt",
    )
    hierarchy = [
        f"Q{item}|P21|{TRAVEL_ROOT}"
        for item in range(3018, 3065)
        if item != 3062
    ]
    (REPO_ROOT / "quickstatements-abstract-hierarchy.txt").write_text(
        "\n".join(hierarchy) + "\n",
        encoding="utf-8",
    )
    countries_csv = REPO_ROOT / "countries.csv"
    cities_csv = REPO_ROOT / "cities.csv"
    if countries_csv.is_file() and cities_csv.is_file():
        country_items = read_assigned_items(countries_csv)
        city_items = read_assigned_items(cities_csv)
        bind_items(
            countries,
            country_items,
            REPO_ROOT / "abstract-countries.csv",
        )
        bind_items(
            cities,
            city_items,
            REPO_ROOT / "abstract-cities.csv",
        )
        write_bound_statements(countries, country_items, cities, city_items)
        print("Bound assigned country and city IDs and wrote relationship batches")
    print(f"Wrote {len(countries)} countries and {len(cities)} cities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
