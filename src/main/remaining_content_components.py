#!/usr/bin/env python3
"""Inventory and bind headings in the non-travel abstract pages."""

from __future__ import annotations

import csv
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

from abstract_quickstatements import LANGUAGES, quickstatements_quote
from bind_abstract_content import HEADING, qid
from content_components_quickstatements import DESCRIPTIONS, headings
from paths import REPO_ROOT
from remaining_abstract_quickstatements import GROUPS


FIXED = {
    "John Samuel": "Q42761025",
    "My Travels": "Q3062",
    "Travel": "Q3062",
}
DYNAMIC_NO_RESULTS = (
    "No results found",
    "Aucun résultat trouvé",
    "ഫലങ്ങളൊന്നും കണ്ടെത്തിയില്ല",
    "ਕੋਈ ਨਤੀਜੇ ਨਹੀਂ ਮਿਲੇ",
    "कोई परिणाम नहीं मिला",
    "Nenhum resultado encontrado",
    "No se encontraron resultados",
    "Nessun risultato trovato",
)


def existing_labels() -> dict[str, str]:
    result = dict(FIXED)
    for export in ("concepts.csv", "abstractid.csv"):
        with (REPO_ROOT / export).open(
            encoding="utf-8-sig", newline=""
        ) as source:
            for row in csv.DictReader(source):
                item = qid(row["item"])
                if item:
                    result.setdefault(row["label"], item)
    return result


def built_pages() -> list[tuple[str, str, Path, dict[str, Path]]]:
    grouped: dict[tuple[str, str, str], dict[str, Path]] = {}
    with (REPO_ROOT / "remaining-abstract-pages.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            key = (row["abstract_item"], row["group"], row["abstract_path"])
            grouped.setdefault(key, {})[row["language"]] = REPO_ROOT / row["path"]
    return [
        (item, group, REPO_ROOT / target, languages)
        for (item, group, target), languages in grouped.items()
    ]


def inventory() -> tuple[
    OrderedDict[tuple[str, ...], str],
    list[tuple[str, int, str]],
    dict[str, str],
]:
    known = existing_labels()
    concepts: OrderedDict[tuple[str, ...], str] = OrderedDict()
    occurrences: list[tuple[str, int, str]] = []
    assigned: dict[str, str] = {}
    for item, _group, target, sources in built_pages():
        abstract = headings(target)
        localized = {language: headings(path) for language, path in sources.items()}
        safe = all(
            [(tag, classes) for tag, classes, _text in localized["en"]]
            == [(tag, classes) for tag, classes, _text in localized[language]]
            for language in LANGUAGES
        )
        for index, (tag, classes, text) in enumerate(abstract):
            if not text or re.fullmatch(r"Q[0-9]+", text):
                continue
            existing = known.get(text)
            if existing:
                token = f"EXISTING:{existing}"
                assigned[token] = existing
                occurrences.append((item, index, token))
                continue
            labels: list[str] = []
            for language in LANGUAGES:
                if safe and index < len(localized[language]):
                    labels.append(localized[language][index][2])
                elif language == "en":
                    labels.append(text)
                else:
                    labels.append("")
            key = tuple(labels)
            token = concepts.setdefault(key, f"R{len(concepts) + 1:04d}")
            occurrences.append((item, index, token))
    return concepts, occurrences, assigned


def write_outputs() -> tuple[int, int, int]:
    concepts, occurrences, assigned = inventory()
    known = existing_labels()
    dynamic_item = known.get(DYNAMIC_NO_RESULTS[0])
    if not dynamic_item:
        concepts.setdefault(
            DYNAMIC_NO_RESULTS,
            f"R{len(concepts) + 1:04d}",
        )
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
        statements.append("LAST|P8|Q3185")
        blocks.append("\n".join(statements))
    (REPO_ROOT / "quickstatements-remaining-content-items.txt").write_text(
        "\n\n".join(blocks) + ("\n" if blocks else ""),
        encoding="utf-8",
    )
    with (REPO_ROOT / "remaining-content-components.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", *LANGUAGES))
        for labels, token in concepts.items():
            writer.writerow((token, *labels))
    with (REPO_ROOT / "remaining-content-occurrences.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("page_item", "heading_index", "token"))
        writer.writerows(occurrences)
    with (REPO_ROOT / "remaining-content-assigned.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "abstract_item"))
        writer.writerows(sorted(assigned.items()))
    changed = apply_assigned(occurrences, assigned)
    if dynamic_item:
        path = REPO_ROOT / "Q315/Q3647.html"
        html = path.read_text(encoding="utf-8")
        updated = html.replace(
            "<h2>No results found</h2>",
            f"<h2>{dynamic_item}</h2>",
        )
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return len(concepts), len(occurrences), changed


def apply_assigned(
    occurrences: list[tuple[str, int, str]], assigned: dict[str, str]
) -> int:
    replacements: dict[str, dict[int, str]] = defaultdict(dict)
    for item, index, token in occurrences:
        if token in assigned:
            replacements[item][index] = assigned[token]
    targets = {item: target for item, _group, target, _sources in built_pages()}
    changed = 0
    for item, indexes in replacements.items():
        path = targets[item]
        html = path.read_text(encoding="utf-8")
        index = -1

        def replace(match: re.Match[str]) -> str:
            nonlocal index
            index += 1
            value = indexes.get(index)
            return (
                f"{match.group(1)}{value}{match.group(4)}"
                if value
                else match.group(0)
            )

        updated = HEADING.sub(replace, html)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def main() -> int:
    concepts, occurrences, changed = write_outputs()
    print(
        f"Wrote {concepts} new content concepts for {occurrences} occurrences; "
        f"applied existing QIDs to {changed} pages"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
