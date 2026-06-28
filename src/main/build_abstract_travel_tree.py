#!/usr/bin/env python3
"""Build the canonical QID path manifest and the first abstract travel pilot."""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path

from abstract_quickstatements import LANGUAGES, clean_title, groups, parse_page
from paths import REPO_ROOT
from place_abstract_quickstatements import city_groups, country_groups


ROOT = REPO_ROOT / "Q315/Q3062"
ARCHITECTURE_ITEM = "Q3019"
MODERN_ARCHITECTURE = REPO_ROOT / "en/photography/architecture.html"


def assigned(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        seen: list[str] = []
        for row in csv.DictReader(source):
            item = row["abstract_item"]
            if item not in seen:
                seen.append(item)
        return seen


def write_tree_manifest() -> None:
    topics = [f"Q{item}" for item in range(3018, 3065)]
    countries = assigned(REPO_ROOT / "abstract-countries.csv")
    cities = assigned(REPO_ROOT / "abstract-cities.csv")
    city_data = city_groups()
    country_by_segment = {
        group["en"].stem: item
        for group, item in zip(country_groups(), countries)
    }
    with (REPO_ROOT / "abstract-tree.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("abstract_path", "item", "kind"))
        writer.writerow(("Q315/Q3062/index.html", "Q3062", "collection-index"))
        for item in topics:
            if item != "Q3062":
                writer.writerow((f"Q315/Q3062/{item}.html", item, "topic"))
        for item in countries:
            writer.writerow(
                (f"Q315/Q3062/Q3026/{item}.html", item, "country")
            )
        for group, item in zip(city_data, cities):
            country_item = country_by_segment[group["en"].parent.name]
            writer.writerow(
                (
                    f"Q315/Q3062/Q3025/{country_item}/{item}.html",
                    item,
                    "city",
                )
            )


def local_place_replacements() -> dict[str, str]:
    replacements = {
        "Q31": "Q3068",
        "Q35": "Q3070",
        "Q33": "Q3072",
        "Q142": "Q3073",
        "Q183": "Q3074",
        "Q38": "Q3077",
        "Q45": "Q3082",
        "Q36": "Q3081",
        "Q29": "Q3085",
        "Q34": "Q3086",
        "Q55": "Q3088",
        "Q237": "Q3089",
    }
    labels_path = REPO_ROOT.parent / "Q42761025/data/labels.csv"
    labels: dict[str, str] = {}
    with labels_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            labels.setdefault(row["en"], row["identifier"])
    with (REPO_ROOT / "cities.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            legacy = labels.get(row["label"])
            if legacy:
                replacements[legacy] = row["item"].rstrip("/").split("/")[-1]
    return replacements


def build_architecture_pilot() -> None:
    architecture = next(
        group for group in groups() if group["en"].stem == "architecture"
    )
    build_abstract_page(
        MODERN_ARCHITECTURE,
        ROOT / f"{ARCHITECTURE_ITEM}.html",
        ARCHITECTURE_ITEM,
        architecture,
    )


def visible_identifiers() -> dict[str, str]:
    visible_text = {
        "John Samuel": "Q42761025",
        "Photography & Travel": "Q3062",
        "Home": "Q315",
        "Travel": "Q3062",
        "Select Language": "Q3062",
        "Saint-Nazaire": "Q3126",
        "Gdańsk": "Q3149",
        "Suomenlinna": "Q3177",
        "Pont-en-Royans": "Q3178",
        "Erfurt": "Q3179",
        "Rothenburg": "Q3180",
        "Porto Bridge": "Q3181",
        "Oude Kerk": "Q3182",
        "Nieuwe Kerk": "Q3184",
    }
    topic_groups = groups()
    for offset, group in enumerate(topic_groups):
        item = f"Q{3018 + offset}"
        for language, path in group.items():
            title = path.stem if path.name != "index.html" else path.parent.name
            visible_text.setdefault(title, item)
    for export in ("countries.csv", "cities.csv"):
        with (REPO_ROOT / export).open(
            encoding="utf-8-sig", newline=""
        ) as source:
            for row in csv.DictReader(source):
                visible_text[row["label"]] = row["item"].rstrip("/").split("/")[-1]
    return visible_text


def build_abstract_page(
    source: Path,
    target: Path,
    item: str,
    language_pages: dict[str, Path],
) -> None:
    html = source.read_text(encoding="utf-8")
    html = html.replace('<html lang="en">', '<html lang="zxx">')
    html = html.replace(
        '<meta content="en" http-equiv="Content-Language" />',
        '<meta content="zxx" http-equiv="Content-Language" />',
    )
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>{item}</title>",
        html,
        count=1,
    )
    visible_text = visible_identifiers()
    source_title = source.stem if source.name != "index.html" else source.parent.name
    visible_text[source_title] = item
    visible_text[source_title.upper()] = item
    page_title = clean_title(parse_page(source).title, "en")
    visible_text[page_title] = item
    visible_text[page_title.upper()] = item
    for label, identifier in sorted(
        visible_text.items(),
        key=lambda value: len(value[0]),
        reverse=True,
    ):
        html = re.sub(
            rf">(\s*){re.escape(label)}(\s*)<",
            rf">\1{identifier}\2<",
            html,
        )
    html = html.replace(" - Photography & Travel", " - Q3062")
    html = re.sub(r'\s+alt="[^"]*"', ' alt=""', html)
    html = html.replace(
        '<h1 class="site-title"><a href="../index.html">Q42761025</a></h1>',
        '<h1 class="site-title"><a href="https://www.wikidata.org/wiki/'
        'Q42761025">Q42761025</a></h1>',
    )
    html = html.replace('href="../travel/index.html"', 'href="./index.html"')
    html = html.replace('href="../index.html"', 'href="../index.html"')
    alternates = []
    for language in LANGUAGES:
        concrete = language_pages[language]
        href = Path(os.path.relpath(concrete, target.parent)).as_posix()
        alternates.append(
            f'    <link rel="alternate" hreflang="{language}" '
            f'href="{href}" />'
        )
    html = html.replace(
        "</head>",
        "    <!-- Generated abstract pilot from Wikibase mappings. -->\n"
        + "\n".join(alternates)
        + "\n</head>",
        1,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def build_all_pages() -> int:
    count = 0
    for offset, group in enumerate(groups()):
        item = f"Q{3018 + offset}"
        target = ROOT / ("index.html" if item == "Q3062" else f"{item}.html")
        build_abstract_page(group["en"], target, item, group)
        count += 1
    country_items = assigned(REPO_ROOT / "abstract-countries.csv")
    countries = country_groups()
    for group, item in zip(countries, country_items):
        build_abstract_page(
            group["en"],
            ROOT / "Q3026" / f"{item}.html",
            item,
            group,
        )
        count += 1
    city_items = assigned(REPO_ROOT / "abstract-cities.csv")
    country_by_segment = {
        group["en"].stem: item for group, item in zip(countries, country_items)
    }
    for group, item in zip(city_groups(), city_items):
        country = country_by_segment[group["en"].parent.name]
        build_abstract_page(
            group["en"],
            ROOT / "Q3025" / country / f"{item}.html",
            item,
            group,
        )
        count += 1
    return count


def main() -> int:
    write_tree_manifest()
    count = build_all_pages()
    from bind_abstract_content import main as bind_content

    bind_content()
    from repair_abstract_links import main as repair_links

    repair_links()
    print(f"Wrote abstract-tree.csv and {count} abstract HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
