#!/usr/bin/env python3
"""Bind imported content concepts to QIDs and apply them to abstract HTML."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from paths import REPO_ROOT


REUSED_ITEMS = {
    "C0109": "Q3037",  # Nature
    "C0144": "Q3023",  # Ceilings
    "C0153": "Q3020",  # Beaches
    "C0179": "Q3022",  # Bridges
    "C0188": "Q3047",  # Stations
    "C0215": "Q3035",  # Lakes
    "C0227": "Q3341",  # Golden hour
    "C0243": "Q3399",  # Pipe Organ
}
QID = re.compile(r"(Q[0-9]+)$")
HEADING = re.compile(
    r"(<h([1-4])\b[^>]*>)(.*?)(</h\2>)",
    flags=re.IGNORECASE | re.DOTALL,
)


def qid(value: str) -> str:
    match = QID.search(value)
    return match.group(1) if match else ""


def components() -> list[dict[str, str]]:
    with (REPO_ROOT / "abstract-content-components.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        return list(csv.DictReader(source))


def imported() -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    with (REPO_ROOT / "concepts.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            item = qid(row["item"])
            if item:
                result[row["label"]].append(item)
    return result


def bindings() -> tuple[dict[str, str], list[dict[str, str]]]:
    by_label = imported()
    result: dict[str, str] = {}
    missing: list[dict[str, str]] = []
    for row in components():
        matches = by_label.get(row["en"], [])
        if len(matches) == 1:
            result[row["token"]] = matches[0]
        elif row["token"] in REUSED_ITEMS:
            result[row["token"]] = REUSED_ITEMS[row["token"]]
        else:
            missing.append(row)
    return result, missing


def write_bindings(bound: dict[str, str]) -> None:
    labels = {row["token"]: row["en"] for row in components()}
    with (REPO_ROOT / "abstract-content-assigned.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "abstract_item", "en"))
        for token in sorted(bound):
            writer.writerow((token, bound[token], labels[token]))


def write_retry(missing: list[dict[str, str]]) -> None:
    descriptions = {
        "en": "language-independent content component used in an abstract page",
        "fr": "composant de contenu indépendant de la langue utilisé dans une page abstraite",
        "ml": "അമൂർത്ത താളിൽ ഉപയോഗിക്കുന്ന ഭാഷാ-സ്വതന്ത്ര ഉള്ളടക്ക ഘടകം",
        "pa": "ਅਮੂਰਤ ਸਫ਼ੇ ਵਿੱਚ ਵਰਤਿਆ ਭਾਸ਼ਾ-ਸੁਤੰਤਰ ਸਮੱਗਰੀ ਭਾਗ",
        "hi": "अमूर्त पृष्ठ में प्रयुक्त भाषा-स्वतंत्र सामग्री घटक",
        "pt": "componente de conteúdo independente do idioma usado numa página abstrata",
        "es": "componente de contenido independiente del idioma usado en una página abstracta",
        "it": "componente di contenuto indipendente dalla lingua usato in una pagina astratta",
    }
    blocks: list[str] = []
    for row in missing:
        statements = ["CREATE"]
        for language in descriptions:
            label = row.get(language, "")
            if label:
                escaped = label.replace("\\", "\\\\").replace('"', '\\"')
                description = descriptions[language].replace('"', '\\"')
                statements.extend(
                    (
                        f'LAST|L{language}|"{escaped}"',
                        f'LAST|D{language}|"{description}"',
                    )
                )
        statements.append("LAST|P8|Q3185")
        blocks.append("\n".join(statements))
    (REPO_ROOT / "quickstatements-retry-abstract-content.txt").write_text(
        "\n\n".join(blocks) + ("\n" if blocks else ""),
        encoding="utf-8",
    )


def target_paths() -> dict[str, Path]:
    result: dict[str, Path] = {}
    with (REPO_ROOT / "abstract-tree.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            result[row["item"]] = REPO_ROOT / row["abstract_path"]
    return result


def apply_bindings(bound: dict[str, str]) -> int:
    occurrences: dict[str, dict[int, str]] = defaultdict(dict)
    with (REPO_ROOT / "abstract-content-occurrences.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            item = bound.get(row["token"])
            if item:
                occurrences[row["page_item"]][int(row["heading_index"])] = item
    changed = 0
    for page_item, replacements in occurrences.items():
        path = target_paths()[page_item]
        html = path.read_text(encoding="utf-8")
        index = -1

        def replace(match: re.Match[str]) -> str:
            nonlocal index
            index += 1
            replacement = replacements.get(index)
            if not replacement:
                return match.group(0)
            return f"{match.group(1)}{replacement}{match.group(4)}"

        updated = HEADING.sub(replace, html)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def main() -> int:
    bound, missing = bindings()
    write_bindings(bound)
    write_retry(missing)
    changed = apply_bindings(bound)
    print(
        f"Bound {len(bound)} concepts; {len(missing)} need creation; "
        f"updated {changed} HTML pages"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
