#!/usr/bin/env python3
"""Bind and build the complete non-travel eight-language abstract pages."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from abstract_quickstatements import clean_title, parse_page
from build_abstract_travel_tree import build_abstract_page
from paths import REPO_ROOT
from remaining_abstract_quickstatements import GROUPS


ABSTRACT_EXPORT = REPO_ROOT / "abstractid.csv"
MISSING_CONCRETE_FIRST = 3576
NESTING = {
    "research": ("Q315", "index.html"),
    "cv-detailed": ("research", None),
    "writings": ("Q315", "index.html"),
    "quotes": ("writings", None),
    "books": ("writings", None),
    "films": ("writings", None),
    "music": ("writings", None),
    "museums": ("writings", None),
    "iohannes": ("writings", None),
}
ABSTRACT_LABELS = {
    "cv-detailed": "Detailed curriculum vitae",
    "search": "Website search",
}
HOME_LINKS = {
    "research/research.html": "../en/research/research.html",
    "teaching/index.html": "../en/teaching/index.html",
    "writings/index.html": "Q3638/index.html",
    "linguistics/index.html": "../en/linguistics/index.html",
    "travel/index.html": "Q3062/index.html",
    "research/index.html": "Q3636/index.html",
    "./writings/Iohannes.html": "Q3638/Q3644.html",
    "./about.html": "Q3633.html",
    "./blog.html": "Q3634.html",
    "./writings/quotes.html": "Q3638/Q3639.html",
    "disclaimer.html": "Q3635.html",
    "./teaching/archives.html": "../en/teaching/archives.html",
    "./travel/index.html": "Q3062/index.html",
    "photography/countries.html": "Q3062/Q3026.html",
    "./research/research.html": "../en/research/research.html",
    "./writings/books-i-read.html": "Q3638/Q3640.html",
    "./writings/films-series-documentaries.html": "Q3638/Q3641.html",
    "linguistics/learning-language.html": "../en/linguistics/learning-language.html",
    "./writings/music.html": "Q3638/Q3642.html",
    "./writings/museums-galleries.html": "Q3638/Q3643.html",
    "./blog/blogs-list.html": "../en/blog/blogs-list.html",
    "./search.html": "Q3647.html",
}


def qid(value: str) -> str:
    match = re.search(r"(Q[0-9]+)$", value)
    return match.group(1) if match else ""


def abstract_bindings() -> dict[str, str]:
    labels: dict[str, str] = {}
    with ABSTRACT_EXPORT.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            labels[row["label"]] = qid(row["item"])
    result = {"home": "Q315"}
    for key, paths in GROUPS.items():
        if key == "home":
            continue
        title = ABSTRACT_LABELS.get(
            key,
            clean_title(parse_page(REPO_ROOT / paths["en"]).title, "en"),
        )
        if title in labels:
            result[key] = labels[title]
    return result


def concrete_bindings() -> dict[str, str]:
    result: dict[str, str] = {}
    with (REPO_ROOT / "pages.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            path = unquote(urlsplit(row["url"]).path).lstrip("/")
            result[path] = qid(row["item"])
    missing = [
        row["path"]
        for row in csv.DictReader(
            (REPO_ROOT / "remaining-abstract-pages.template.csv").open(
                encoding="utf-8-sig", newline=""
            )
        )
        if row["path"] not in result
    ]
    for offset, path in enumerate(dict.fromkeys(missing)):
        result[path] = f"Q{MISSING_CONCRETE_FIRST + offset}"
    return result


def target_for(key: str, item: str, bound: dict[str, str]) -> Path:
    if key == "home":
        return REPO_ROOT / "Q315/index.html"
    parent, filename = NESTING.get(key, ("Q315", None))
    if filename == "index.html":
        return REPO_ROOT / "Q315" / item / "index.html"
    parent_item = bound[parent] if parent in bound else parent
    directory = REPO_ROOT / "Q315"
    if parent_item != "Q315":
        directory /= parent_item
    return directory / f"{item}.html"


def write_manifests(
    abstract: dict[str, str], concrete: dict[str, str]
) -> None:
    links: list[str] = []
    rows: list[tuple[str, str, str, str, str]] = []
    hierarchy: list[str] = []
    for key, item in abstract.items():
        target = target_for(key, item, abstract)
        for language, relative in GROUPS[key].items():
            links.append(f"{concrete[relative]}|P12|{item}")
            rows.append(
                (
                    item,
                    key,
                    language,
                    relative,
                    target.relative_to(REPO_ROOT).as_posix(),
                )
            )
        if key != "home":
            parent = NESTING.get(key, ("Q315", None))[0]
            parent_item = abstract.get(parent, parent)
            hierarchy.append(f"{item}|P21|{parent_item}")
    (REPO_ROOT / "quickstatements-link-remaining-pages.txt").write_text(
        "\n".join(links) + "\n", encoding="utf-8"
    )
    (REPO_ROOT / "quickstatements-remaining-hierarchy.txt").write_text(
        "\n".join(hierarchy) + "\n", encoding="utf-8"
    )
    with (REPO_ROOT / "remaining-abstract-pages.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(
            ("abstract_item", "group", "language", "path", "abstract_path")
        )
        writer.writerows(rows)
    recovered = [
        (path, item)
        for path, item in concrete.items()
        if MISSING_CONCRETE_FIRST <= int(item[1:]) <= 3630
    ]
    with (REPO_ROOT / "remaining-concrete-pages-recovered.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("path", "item"))
        writer.writerows(recovered)


def build(abstract: dict[str, str]) -> int:
    count = 0
    for key, item in abstract.items():
        pages = {
            language: REPO_ROOT / relative
            for language, relative in GROUPS[key].items()
        }
        build_abstract_page(
            pages["en"],
            target_for(key, item, abstract),
            item,
            pages,
        )
        if key == "home":
            html = target_for(key, item, abstract).read_text(encoding="utf-8")
            for old, new in HOME_LINKS.items():
                html = html.replace(f'href="{old}"', f'href="{new}"')
            target_for(key, item, abstract).write_text(html, encoding="utf-8")
        count += 1
    return count


def main() -> int:
    abstract = abstract_bindings()
    concrete = concrete_bindings()
    write_manifests(abstract, concrete)
    count = build(abstract)
    from repair_abstract_links import main as repair_links

    repair_links()
    missing = sorted(set(GROUPS) - set(abstract))
    print(
        f"Built {count} non-travel abstract pages; "
        f"unbound groups: {', '.join(missing) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
