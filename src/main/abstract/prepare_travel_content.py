#!/usr/bin/env python3
"""Inventory remaining travel text and prepare deduplicated QuickStatements."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_MANIFEST, DEFAULT_REPO_ROOT, load_groups


LANGUAGES = ("en", "fr", "ml", "pa", "hi", "pt", "es", "it")
TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "a", "span", "button", "label", "li", "figcaption"}
QID_TEXT = re.compile(r"(?:Q[0-9]+\s*)+")
MOJIBAKE_MARKERS = ("Ã", "â")
DEFAULT_DATA = DEFAULT_REPO_ROOT.parent / "Q42761025" / "data"
DEFAULT_OUTPUT = HERE / "travel-content.quickstatements"
DEFAULT_MANIFEST_OUTPUT = HERE / "travel-content-manifest.csv"
DEFAULT_PENDING_MANIFEST_OUTPUT = HERE / "travel-content-pending-manifest.csv"
DEFAULT_MISSING = HERE / "travel-content-missing.csv"
DEFAULT_BINDINGS_OUTPUT = HERE / "travel-content-bindings.csv"
DEFAULT_OVERRIDES = HERE / "travel-content-overrides.csv"
DEFAULT_GENERATED_TRANSLATIONS = HERE / "travel-content-generated-translations.csv"
MONOLINGUAL_CONTENT_PROPERTY = "P40"
LABEL_LIMIT = 250
TRAVEL_CONTENT_EXCLUDED_QIDS = {"Q3838", "Q3839", "Q3840", "Q3841"}


class DirectTextSlots(HTMLParser):
    """Collect direct text by stable element signature and occurrence."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, tuple[str, str, str, int], list[str]]] = []
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.slots: dict[tuple[str, str, str, int], str] = {}
        self.content: dict[tuple[str, str, str, int], str] = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        base = (
            tag,
            ".".join(sorted((values.get("class") or "").split())),
            values.get("role") or "",
        )
        index = self.counts[base]
        self.counts[base] += 1
        key = (*base, index)
        data_content = values.get("data-content") or ""
        if data_content.startswith("local:"):
            self.content[key] = data_content.removeprefix("local:")
        self.stack.append((tag, key, []))

    def handle_endtag(self, tag):
        if tag not in [entry[0] for entry in self.stack]:
            return
        while self.stack:
            current, key, parts = self.stack.pop()
            text = " ".join("".join(parts).split())
            if current in TEXT_TAGS and text:
                self.slots[key] = repair_mojibake(text)
            if current == tag:
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][2].append(data)


def slots(path: Path) -> dict[tuple[str, str, str, int], str]:
    parser = DirectTextSlots()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.slots


def repair_mojibake(value: str) -> str:
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value
    if sum(value.count(marker) for marker in MOJIBAKE_MARKERS) > sum(
        repaired.count(marker) for marker in MOJIBAKE_MARKERS
    ):
        return repaired
    return value


def content_bindings(path: Path) -> dict[tuple[str, str, str, int], str]:
    parser = DirectTextSlots()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.content


def known_english(data_dir: Path) -> set[str]:
    values: set[str] = set()
    for name in (
        "abstract-content-items.csv",
        "labels-wikibase.csv",
        "labels.csv",
        "concepts.csv",
    ):
        path = data_dir / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("en"):
                    values.add(row["en"].strip().casefold())
    return values


def local_id(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def exported_text(value: str) -> str:
    return value.strip().replace('\\"', '"')


def existing_content(data_dir: Path) -> dict[tuple[str, ...], str]:
    existing: dict[tuple[str, ...], str] = {}

    values_path = data_dir / "abstract-content-values.csv"
    if values_path.exists():
        by_item: dict[str, dict[str, str]] = {}
        with values_path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                item = row.get("item", "").strip()
                language = row.get("language", "").strip()
                text = exported_text(row.get("text", ""))
                if item and language and text:
                    by_item.setdefault(item, {})[language] = text
        for item, labels in by_item.items():
            values = tuple(labels.get(language, "") for language in LANGUAGES)
            if any(values):
                existing.setdefault(values, local_id(item))

    items_path = data_dir / "abstract-content-items.csv"
    if items_path.exists():
        with items_path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                item = row.get("item", "").strip()
                values = tuple(
                    exported_text(row.get(language, "")) for language in LANGUAGES
                )
                if item and any(values):
                    existing.setdefault(
                        values,
                        local_id(item),
                    )

    labels_path = data_dir / "labels-wikibase.csv"
    if labels_path.exists():
        with labels_path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("itemtype") and row["itemtype"].strip() != "Q3185":
                    continue
                identifier = row.get("identifier", "").strip()
                values = tuple(
                    exported_text(row.get(language, "")) for language in LANGUAGES
                )
                if re.fullmatch(r"Q[0-9]+", identifier) and any(values):
                    existing.setdefault(
                        values,
                        identifier,
                    )

    return existing


def load_overrides(path: Path) -> dict[tuple[str, str, str, str, int], str]:
    if not path.exists():
        return {}
    overrides: dict[tuple[str, str, str, str, int], str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            page = row.get("page", "").strip()
            qid = row.get("qid", "").strip()
            if not page or not qid:
                continue
            if not re.fullmatch(r"Q[0-9]+", qid):
                raise ValueError(f"{path}: invalid override QID {qid!r}")
            key = (
                page,
                row.get("tag", "").strip(),
                row.get("class", "").strip(),
                row.get("role", "").strip(),
                int(row.get("occurrence", "0")),
            )
            previous = overrides.get(key)
            if previous and previous != qid:
                raise ValueError(f"{path}: conflicting overrides for {key}")
            overrides[key] = qid
    return overrides


def load_generated_translations(
    path: Path,
) -> dict[tuple[str, str, str, str, int], dict[str, str]]:
    if not path.exists():
        return {}
    translations: dict[tuple[str, str, str, str, int], dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            page = row.get("page", "").strip()
            if not page:
                continue
            key = (
                page,
                row.get("tag", "").strip(),
                row.get("class", "").strip(),
                row.get("role", "").strip(),
                int(row.get("occurrence", "0")),
            )
            values = {
                language: row.get(language, "").strip()
                for language in LANGUAGES
                if row.get(language, "").strip()
            }
            if values:
                translations[key] = values
    return translations


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def monolingual_value(language: str, value: str) -> str:
    return f'{language}:"{quote(value)}"'


def quickstatement_blocks(text: str) -> list[list[str]]:
    return [
        [line for line in block.splitlines() if line.strip()]
        for block in re.split(r"\n\s*\n", text.strip())
        if block.strip()
    ]


def validate_quickstatements(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]

    errors: list[str] = []
    label_prefixes = {
        language: f"LAST|L{language}|"
        for language in LANGUAGES
    }
    label_prefixes["en"] = "LAST|Len|"
    content_prefixes = {
        language: f"LAST|{MONOLINGUAL_CONTENT_PROPERTY}|{language}:"
        for language in LANGUAGES
    }

    for index, block in enumerate(quickstatement_blocks(path.read_text(encoding="utf-8")), 1):
        if not block or block[0] != "CREATE":
            errors.append(f"block {index}: expected CREATE")
            continue
        for language, prefix in content_prefixes.items():
            if not any(line.startswith(prefix) for line in block):
                errors.append(f"block {index}: missing {MONOLINGUAL_CONTENT_PROPERTY} {language}")

        english_labels = [line for line in block if line.startswith("LAST|Len|")]
        token_only_label = (
            len(english_labels) == 1
            and english_labels[0].endswith(' content"')
        )
        if token_only_label:
            continue
        for language, prefix in label_prefixes.items():
            if not any(line.startswith(prefix) for line in block):
                errors.append(f"block {index}: missing label {language}")

    return errors


def prepare(
    repo_root: Path,
    data_dir: Path,
    output: Path,
    manifest: Path,
    pending_manifest: Path,
    missing: Path,
    bindings: Path,
    overrides_path: Path = DEFAULT_OVERRIDES,
    generated_translations_path: Path = DEFAULT_GENERATED_TRANSLATIONS,
) -> tuple[int, int, int]:
    known = known_english(data_dir)
    existing = existing_content(data_dir)
    overrides = load_overrides(overrides_path)
    generated_translations = load_generated_translations(generated_translations_path)
    concepts: dict[tuple[str, ...], str] = {}
    bound: dict[str, str] = {}
    occurrences: list[tuple[str, str, str, str, int]] = []
    pending_occurrences: list[tuple[str, str, str, str, str, int]] = []
    incomplete: list[tuple[str, str, str, int, str, str]] = []
    for group in load_groups(DEFAULT_MANIFEST, repo_root):
        pages = [slots(repo_root / page) for page in group.pages]
        bound_slots = content_bindings(repo_root / group.pages[0])
        for key, qid in bound_slots.items():
            if qid in TRAVEL_CONTENT_EXCLUDED_QIDS:
                continue
            occurrences.append((group.identifier, qid, *key))
            bound[qid] = qid
        for key, abstract_text in pages[0].items():
            if key in bound_slots:
                continue
            if QID_TEXT.fullmatch(abstract_text):
                continue
            localized = list(page.get(key, "") for page in pages[1:])
            generated = generated_translations.get((group.identifier, *key), {})
            for index, language in enumerate(LANGUAGES):
                if not localized[index] and generated.get(language):
                    localized[index] = generated[language]
            localized = tuple(localized)
            if not all(localized):
                absent = ",".join(
                    language for language, value in zip(LANGUAGES, localized) if not value
                )
                incomplete.append((group.identifier, *key, abstract_text, absent))
                qid = overrides.get((group.identifier, *key)) or existing.get(localized)
                if qid:
                    token = qid
                    bound[token] = qid
                    occurrences.append((group.identifier, token, *key))
                continue
            values = localized
            copied = [
                language
                for language, value in zip(LANGUAGES[1:], values[1:])
                if len(values[0]) > 30 and value.casefold() == values[0].casefold()
            ]
            if copied:
                incomplete.append(
                    (group.identifier, *key, abstract_text, "copied:" + ",".join(copied))
                )
            qid = overrides.get((group.identifier, *key)) or existing.get(values)
            if qid:
                token = qid
                bound[token] = qid
                occurrences.append((group.identifier, token, *key))
                continue
            if values[0].casefold() in known:
                continue
            token = concepts.setdefault(values, f"T{len(concepts) + 1:04d}")
            pending_occurrences.append((group.identifier, token, *key))

    blocks = []
    for values, token in concepts.items():
        statements = ["CREATE"]
        if all(len(value) <= LABEL_LIMIT for value in values):
            for language, value in zip(LANGUAGES, values):
                statements.append(f'LAST|L{language}|"{quote(value)}"')
        else:
            statements.append(f'LAST|Len|"{token} travel content"')
        statements.extend(
            f"LAST|{MONOLINGUAL_CONTENT_PROPERTY}|{monolingual_value(language, value)}"
            for language, value in zip(LANGUAGES, values)
        )
        statements.extend(
            (
                'LAST|Den|"language-independent content component used by a travel page"',
                "LAST|P8|Q3185",
            )
        )
        blocks.append("\n".join(statements))
    output.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    with manifest.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("page", "token", "tag", "class", "role", "occurrence"))
        writer.writerows(occurrences)
    with pending_manifest.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("page", "token", "tag", "class", "role", "occurrence"))
        writer.writerows(pending_occurrences)
    with missing.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("page", "tag", "class", "role", "occurrence", "abstract_text", "missing_languages"))
        writer.writerows(incomplete)
    with bindings.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "qid"))
        writer.writerows(sorted(bound.items(), key=lambda row: int(row[1][1:])))
    return len(concepts), len(incomplete), len(bound)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--pending-manifest", type=Path, default=DEFAULT_PENDING_MANIFEST_OUTPUT)
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS_OUTPUT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument(
        "--generated-translations",
        type=Path,
        default=DEFAULT_GENERATED_TRANSLATIONS,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate generated QuickStatements without regenerating them",
    )
    args = parser.parse_args()
    if args.check:
        errors = validate_quickstatements(args.output)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if errors:
            return 1
        print(f"Validated {args.output}")
        return 0
    try:
        created, missing, bound = prepare(
            args.repo_root.resolve(),
            args.data_dir,
            args.output,
            args.manifest,
            args.pending_manifest,
            args.missing,
            args.bindings,
            args.overrides,
            args.generated_translations,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"Prepared {created} unmatched content items; "
        f"{bound} existing items bound; {missing} slots require review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
