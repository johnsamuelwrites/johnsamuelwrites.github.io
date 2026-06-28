#!/usr/bin/env python3
"""Inventory unresolved headings and generate abstract content QuickStatements."""

from __future__ import annotations

import csv
import re
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path

from abstract_quickstatements import LANGUAGES, groups, quickstatements_quote
from paths import REPO_ROOT
from place_abstract_quickstatements import city_groups, country_groups


CLASS_PLACEHOLDER = "Q_ABSTRACT_CONTENT_CLASS"
DESCRIPTIONS = {
    "en": "language-independent content component used in an abstract page",
    "fr": "composant de contenu indépendant de la langue utilisé dans une page abstraite",
    "ml": "അമൂർത്ത താളിൽ ഉപയോഗിക്കുന്ന ഭാഷാ-സ്വതന്ത്ര ഉള്ളടക്ക ഘടകം",
    "pa": "ਅਮੂਰਤ ਸਫ਼ੇ ਵਿੱਚ ਵਰਤਿਆ ਭਾਸ਼ਾ-ਸੁਤੰਤਰ ਸਮੱਗਰੀ ਭਾਗ",
    "hi": "अमूर्त पृष्ठ में प्रयुक्त भाषा-स्वतंत्र सामग्री घटक",
    "pt": "componente de conteúdo independente do idioma usado numa página abstrata",
    "es": "componente de contenido independiente del idioma usado en una página abstracta",
    "it": "componente di contenuto indipendente dalla lingua usato in una pagina astratta",
}


class HeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tag: str | None = None
        self.attrs: dict[str, str | None] = {}
        self.parts: list[str] = []
        self.headings: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4"} and self.tag is None:
            self.tag = tag
            self.attrs = dict(attrs)
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == self.tag:
            text = " ".join("".join(self.parts).split())
            classes = self.attrs.get("class") or ""
            self.headings.append((tag, classes, text))
            self.tag = None

    def handle_data(self, data: str) -> None:
        if self.tag:
            self.parts.append(data)


def headings(path: Path) -> list[tuple[str, str, str]]:
    parser = HeadingParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.headings


def assigned(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        values: list[str] = []
        for row in csv.DictReader(source):
            item = row["abstract_item"]
            if item not in values:
                values.append(item)
        return values


def page_sets() -> list[tuple[str, Path, dict[str, Path]]]:
    result: list[tuple[str, Path, dict[str, Path]]] = []
    root = REPO_ROOT / "Q315/Q3062"
    for offset, group in enumerate(groups()):
        item = f"Q{3018 + offset}"
        target = root / ("index.html" if item == "Q3062" else f"{item}.html")
        result.append((item, target, group))
    countries = country_groups()
    country_items = assigned(REPO_ROOT / "abstract-countries.csv")
    for group, item in zip(countries, country_items):
        result.append((item, root / "Q3026" / f"{item}.html", group))
    country_by_segment = {
        group["en"].stem: item for group, item in zip(countries, country_items)
    }
    for group, item in zip(
        city_groups(),
        assigned(REPO_ROOT / "abstract-cities.csv"),
    ):
        country = country_by_segment[group["en"].parent.name]
        result.append(
            (item, root / "Q3025" / country / f"{item}.html", group)
        )
    return result


def unresolved() -> tuple[
    OrderedDict[tuple[str, ...], str],
    list[tuple[str, int, str, str, str]],
    list[str],
]:
    concepts: OrderedDict[tuple[str, ...], str] = OrderedDict()
    occurrences: list[tuple[str, int, str, str, str]] = []
    warnings: list[str] = []
    for page_item, abstract_path, language_paths in page_sets():
        abstract_headings = headings(abstract_path)
        localized = {
            language: headings(path)
            for language, path in language_paths.items()
        }
        localized_roles: dict[
            str,
            dict[tuple[str, str], list[str]],
        ] = {}
        for language, values in localized.items():
            roles: dict[tuple[str, str], list[str]] = {}
            for tag, classes, text in values:
                roles.setdefault((tag, classes), []).append(text)
            localized_roles[language] = roles
        english_role_counts = {
            role: len(values)
            for role, values in localized_roles["en"].items()
        }
        page_unsafe = any(
            {
                role: len(values)
                for role, values in localized_roles[language].items()
            }
            != english_role_counts
            for language in LANGUAGES
        )
        if page_unsafe and page_item not in warnings:
            warnings.append(page_item)
        role_indexes: dict[tuple[str, str], int] = {}
        for index, (tag, classes, abstract_text) in enumerate(abstract_headings):
            role = (tag, classes)
            role_index = role_indexes.get(role, 0)
            role_indexes[role] = role_index + 1
            if not abstract_text or re.fullmatch(r"Q[0-9]+", abstract_text):
                continue
            labels: list[str] = []
            for language in LANGUAGES:
                if page_unsafe and language != "en":
                    labels.append("")
                    continue
                values = localized_roles[language].get(role, [])
                if role_index < len(values):
                    label = values[role_index]
                else:
                    label = abstract_text
                    if page_item not in warnings:
                        warnings.append(page_item)
                labels.append(label or abstract_text)
            key = tuple(labels)
            token = concepts.setdefault(key, f"C{len(concepts) + 1:04d}")
            occurrences.append(
                (
                    page_item,
                    index,
                    tag,
                    classes,
                    token,
                )
            )
    return concepts, occurrences, warnings


def write_outputs() -> tuple[int, int, int]:
    concepts, occurrences, warnings = unresolved()
    blocks: list[str] = []
    for labels, _token in concepts.items():
        statements = ["CREATE"]
        for language, label in zip(LANGUAGES, labels):
            if not label:
                continue
            statements.append(
                f'LAST|L{language}|"{quickstatements_quote(label)}"'
            )
            statements.append(
                f'LAST|D{language}|'
                f'"{quickstatements_quote(DESCRIPTIONS[language])}"'
            )
        statements.append(f"LAST|P8|{CLASS_PLACEHOLDER}")
        blocks.append("\n".join(statements))
    (REPO_ROOT / "quickstatements-abstract-content-items.template.txt").write_text(
        "\n\n".join(blocks) + "\n",
        encoding="utf-8",
    )
    with (REPO_ROOT / "abstract-content-occurrences.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("page_item", "heading_index", "tag", "class", "token"))
        writer.writerows(occurrences)
    with (REPO_ROOT / "abstract-content-components.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", *LANGUAGES))
        for labels, token in concepts.items():
            writer.writerow((token, *labels))
    (REPO_ROOT / "abstract-content-alignment-warnings.txt").write_text(
        "\n".join(warnings) + ("\n" if warnings else ""),
        encoding="utf-8",
    )
    return len(concepts), len(occurrences), len(warnings)


def main() -> int:
    concepts, occurrences, warnings = write_outputs()
    print(
        f"Wrote {concepts} content items for {occurrences} occurrences; "
        f"{warnings} pages need alignment review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
