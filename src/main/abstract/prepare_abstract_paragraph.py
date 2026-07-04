#!/usr/bin/env python3
"""Prepare abstract-paragraph items and bind real Wikibase QIDs after import.

The page, its composed-paragraph identity, labels, and target CSS class all
come from a pilot descriptor (``--pilot``) rather than being hard-coded, so the
same tool bootstraps a composed paragraph on any abstract page.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Sequence


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def load_pilot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def page_qid(pilot: dict) -> str:
    page = pilot.get("page", "")
    return page.removeprefix("local:") if page.startswith("local:") else page


def paragraph_class(pilot: dict) -> str:
    css_class = pilot.get("paragraph_class", "")
    if not css_class:
        raise ValueError("pilot descriptor must define 'paragraph_class'")
    return css_class


def paragraph_regex(pilot: dict) -> re.Pattern[str]:
    css_class = re.escape(paragraph_class(pilot))
    return re.compile(
        rf'(?P<indent>^[ \t]*)<p\s+class="{css_class}"[^>]*>.*?</p>',
        flags=re.MULTILINE | re.DOTALL,
    )


def missing_translations(pilot: dict) -> dict[str, list[str]]:
    required = pilot["required_languages"]
    return {
        part["token"]: [
            language for language in required if language not in part["values"]
        ]
        for part in pilot["parts"]
    }


def quickstatements(
    pilot: dict, bindings: dict[str, str] | None = None
) -> str:
    bindings = bindings or {}
    blocks: list[str] = []
    for item_class in pilot["ontology"]["classes"]:
        if bindings.get(item_class["token"]):
            continue
        blocks.append(
            "\n".join(
                (
                    "CREATE",
                    f'LAST|Len|"{quote(item_class["label"])}"',
                    f'LAST|Den|"{quote(item_class["description"])}"',
                )
            )
        )
    if not bindings.get(pilot["function_token"]):
        function_label = pilot.get("function_label", "concatenate monolingual text")
        function_description = pilot.get(
            "function_description",
            "deterministic abstract function joining ordered monolingual "
            "text parts",
        )
        blocks.append(
            "\n".join(
                (
                    "CREATE",
                    f'LAST|Len|"{quote(function_label)}"',
                    f'LAST|Den|"{quote(function_description)}"',
                )
            )
        )

    if not bindings.get(pilot["paragraph_token"]):
        paragraph_label = pilot.get(
            "paragraph_label", f"{page_qid(pilot)} composed paragraph"
        )
        paragraph_description = pilot.get(
            "paragraph_description",
            "language-independent paragraph composed from abstract content items",
        )
        blocks.append(
            "\n".join(
                (
                    "CREATE",
                    f'LAST|Len|"{quote(paragraph_label)}"',
                    f'LAST|Den|"{quote(paragraph_description)}"',
                    "LAST|P8|Q3185",
                )
            )
        )
    for part in pilot["parts"]:
        if bindings.get(part["token"]):
            continue
        statements = ["CREATE"]
        for language, value in part["values"].items():
            statements.append(f'LAST|L{language}|"{quote(value)}"')
        statements.extend(
            (
                'LAST|Den|"language-independent sentence used in an '
                'abstract paragraph"',
                "LAST|P8|Q3185",
            )
        )
        blocks.append("\n".join(statements))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def read_bindings(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source)
        return {row["token"]: row["qid"] for row in rows}


def item_tokens(pilot: dict) -> list[str]:
    return [
        *(item_class["token"] for item_class in pilot["ontology"]["classes"]),
        pilot["function_token"],
        pilot["paragraph_token"],
        *(part["token"] for part in pilot["parts"]),
    ]


def property_tokens(pilot: dict) -> list[str]:
    return [prop["token"] for prop in pilot["ontology"]["properties"]]


def validate_bindings(
    pilot: dict, bindings: dict[str, str], include_ontology: bool = True
) -> list[str]:
    tokens = item_tokens(pilot) if include_ontology else [
        pilot["function_token"],
        pilot["paragraph_token"],
        *(part["token"] for part in pilot["parts"]),
    ]
    errors: list[str] = []
    for token in tokens:
        value = bindings.get(token, "")
        if not value.startswith("Q") or not value[1:].isdigit():
            errors.append(f"{token}: missing or invalid local QID {value!r}")
    valid_item_values = [
        bindings[token]
        for token in tokens
        if bindings.get(token, "").startswith("Q")
        and bindings[token][1:].isdigit()
    ]
    if len(set(valid_item_values)) != len(valid_item_values):
        errors.append("every pilot token must be bound to a distinct QID")
    if include_ontology:
        for token in property_tokens(pilot):
            value = bindings.get(token, "")
            if not value.startswith("P") or not value[1:].isdigit():
                errors.append(f"{token}: missing or invalid property ID {value!r}")
    return errors


def write_binding_template(pilot: dict, path: Path) -> None:
    existing = read_bindings(path) if path.exists() else {}
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "qid"))
        for token in (*item_tokens(pilot), *property_tokens(pilot)):
            writer.writerow((token, existing.get(token, "")))


def write_property_schema(pilot: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "label", "datatype", "description"))
        for prop in pilot["ontology"]["properties"]:
            writer.writerow(
                (
                    prop["token"],
                    prop["label"],
                    prop["datatype"],
                    prop["description"],
                )
            )


def structural_quickstatements(pilot: dict, bindings: dict[str, str]) -> str:
    instance_of = pilot["ontology"]["existing_properties"]["instance_of"]
    part_of = pilot["ontology"]["existing_properties"]["part_of"]
    content_property = bindings["MONOLINGUAL_CONTENT_PROPERTY"]
    constructor_property = bindings["CONSTRUCTOR_FUNCTION_PROPERTY"]
    ordinal_property = bindings["SEQUENCE_ORDINAL_PROPERTY"]
    function = bindings[pilot["function_token"]]
    paragraph = bindings[pilot["paragraph_token"]]
    statements = [
        f'{function}|{instance_of}|{bindings["ABSTRACT_FUNCTION_CLASS"]}',
        f'{paragraph}|{instance_of}|{bindings["ABSTRACT_PARAGRAPH_CLASS"]}',
        f"{paragraph}|{part_of}|{page_qid(pilot)}",
        f"{paragraph}|{constructor_property}|{function}",
    ]
    for index, part in enumerate(pilot["parts"], 1):
        sentence = bindings[part["token"]]
        statements.extend(
            (
                f'{sentence}|{instance_of}|{bindings["ABSTRACT_SENTENCE_CLASS"]}',
                f'{sentence}|{part_of}|{paragraph}|{ordinal_property}|"{index}"',
            )
        )
        for language, value in part["values"].items():
            statements.append(
                f'{sentence}|{content_property}|'
                f'{language}:"{quote(value)}"'
            )
    return "\n".join(statements) + "\n"


def prepare(
    pilot_path: Path, output: Path, bindings: Path, properties: Path
) -> int:
    pilot = load_pilot(pilot_path)
    existing = read_bindings(bindings) if bindings.exists() else {}
    output.write_text(
        quickstatements(pilot, bindings=existing), encoding="utf-8"
    )
    write_binding_template(pilot, bindings)
    write_property_schema(pilot, properties)
    missing = missing_translations(pilot)
    count = sum(len(languages) for languages in missing.values())
    print(f"Wrote {output}, {bindings}, and {properties}")
    print(f"Missing {count} sentence translations:")
    for token, languages in missing.items():
        if languages:
            print(f"  {token}: {', '.join(languages)}")
    return 0


def check(pilot_path: Path, bindings: Path) -> int:
    pilot = load_pilot(pilot_path)
    errors = validate_bindings(pilot, read_bindings(bindings))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"{page_qid(pilot)} paragraph pilot has complete real-QID bindings")
    return 0


def write_structure(pilot_path: Path, bindings_path: Path, output: Path) -> int:
    pilot = load_pilot(pilot_path)
    bindings = read_bindings(bindings_path)
    errors = validate_bindings(pilot, bindings)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    output.write_text(
        structural_quickstatements(pilot, bindings), encoding="utf-8"
    )
    print(f"Wrote queryable structural statements to {output}")
    return 0


def abstract_markup(pilot: dict, bindings: dict[str, str], indent: str) -> str:
    paragraph = bindings[pilot["paragraph_token"]]
    function = bindings[pilot["function_token"]]
    child = indent + "    "
    grandchild = child + "    "
    lines = [
        f'{indent}<p id="{paragraph}" class="{paragraph_class(pilot)}" '
        f'data-content="local:{paragraph}">',
        f'{child}<q-call data-function="local:{function}">',
        f'{grandchild}<q-arg data-name="parts">',
    ]
    item_indent = grandchild + "    "
    for part in pilot["parts"]:
        qid = bindings[part["token"]]
        lines.append(
            f'{item_indent}<span data-content="local:{qid}">{qid}</span>'
        )
    lines.extend(
        (
            f"{grandchild}</q-arg>",
            f"{child}</q-call>",
            f"{indent}</p>",
        )
    )
    return "\n".join(lines)


def bind(pilot_path: Path, bindings_path: Path, abstract_page: Path) -> int:
    pilot = load_pilot(pilot_path)
    bindings = read_bindings(bindings_path)
    errors = validate_bindings(pilot, bindings, include_ontology=False)
    missing = missing_translations(pilot)
    for token, languages in missing.items():
        if languages:
            errors.append(f"{token}: missing translations {', '.join(languages)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("Q315 was not changed")
        return 1

    regex = paragraph_regex(pilot)
    source = abstract_page.read_text(encoding="utf-8")
    match = regex.search(source)
    if match is None:
        paragraph_qid = bindings[pilot["paragraph_token"]]
        if (
            f'data-content="local:{paragraph_qid}"' in source
            and "<q-call" in source
        ):
            print(f"{page_qid(pilot)} paragraph pilot is already bound")
            return 0
        print(
            "ERROR: expected exactly one unbound "
            f'"{paragraph_class(pilot)}" paragraph'
        )
        print("Q315 was not changed")
        return 1
    if len(regex.findall(source)) != 1:
        print(
            "ERROR: expected exactly one unbound "
            f'"{paragraph_class(pilot)}" paragraph'
        )
        print("Q315 was not changed")
        return 1

    replacement = abstract_markup(pilot, bindings, match.group("indent"))
    abstract_page.write_text(
        regex.sub(replacement, source, count=1),
        encoding="utf-8",
    )
    print(f"Bound {page_qid(pilot)} abstract markup in {abstract_page}")
    return 0


def default_abstract_page(pilot_path: Path) -> Path:
    return REPO_ROOT / "Q315" / page_qid(load_pilot(pilot_path)) / "index.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot",
        type=Path,
        required=True,
        help="abstract-paragraph descriptor JSON",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--output", type=Path)
    prepare_parser.add_argument("--bindings", type=Path)
    prepare_parser.add_argument("--properties", type=Path)
    check_parser = subparsers.add_parser("check-bindings")
    check_parser.add_argument("--bindings", type=Path)
    structure_parser = subparsers.add_parser("write-structure")
    structure_parser.add_argument("--bindings", type=Path)
    structure_parser.add_argument("--output", type=Path)
    bind_parser = subparsers.add_parser("bind")
    bind_parser.add_argument("--bindings", type=Path)
    bind_parser.add_argument("--abstract-page", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pilot = args.pilot
    stem = pilot.stem
    bindings = getattr(args, "bindings", None) or pilot.with_name(f"{stem}-bindings.csv")
    if args.command == "prepare":
        output = args.output or pilot.with_name(f"{stem}.quickstatements")
        properties = args.properties or pilot.with_name(f"{stem}-properties.csv")
        return prepare(pilot, output, bindings, properties)
    if args.command == "check-bindings":
        return check(pilot, bindings)
    if args.command == "write-structure":
        output = args.output or pilot.with_name(f"{stem}-structure.quickstatements")
        return write_structure(pilot, bindings, output)
    abstract_page = args.abstract_page or default_abstract_page(pilot)
    return bind(pilot, bindings, abstract_page)


if __name__ == "__main__":
    raise SystemExit(main())
