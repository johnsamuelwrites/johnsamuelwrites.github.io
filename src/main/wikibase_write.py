#!/usr/bin/env python3
"""Validate or import project QuickStatements through the Wikibase API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from wikibase_api import DEFAULT_API, WikibaseClient


ENTITY_RE = re.compile(r"^(?:Q|P)\d+$")
TERM_RE = re.compile(r"^([LDA])([a-z][a-z0-9-]*)$")
PROPERTY_RE = re.compile(r"^P\d+$")
MONOLINGUAL_RE = re.compile(r'^([a-z][a-z0-9-]*):"(.*)"$', re.DOTALL)


def load_env(path: Path) -> None:
    """Load simple KEY=VALUE credentials without replacing shell values."""
    if not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(
            f"{path} permissions are {mode:04o}; use chmod 600 {path}"
        )
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"{path}:{number}: invalid environment variable name")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass
class Operation:
    subject: str | None
    lines: list[tuple[int, list[str]]] = field(default_factory=list)

    @property
    def key(self) -> str:
        text = "\n".join("|".join(parts) for _, parts in self.lines)
        return hashlib.sha256(text.encode()).hexdigest()


def split_line(line: str) -> list[str]:
    return next(csv.reader([line], delimiter="|", quotechar='"', escapechar="\\"))


def parse(path: Path) -> list[Operation]:
    operations: list[Operation] = []
    current: Operation | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = split_line(line)
        subject = parts[0]
        if subject == "CREATE":
            current = Operation(None, [(number, parts)])
            operations.append(current)
        elif ENTITY_RE.fullmatch(subject):
            # Consecutive statements for one existing entity belong in one
            # wbeditentity request. Besides being substantially faster for
            # multilingual label batches, this avoids exhausting Wikibase's
            # edit throttle eight times per item.
            if current is not None and current.subject == subject:
                current.lines.append((number, parts))
            else:
                current = Operation(subject, [(number, parts)])
                operations.append(current)
        elif subject == "LAST":
            if current is None or current.subject is not None:
                raise ValueError(f"{path}:{number}: LAST must follow CREATE")
            current.lines.append((number, parts))
        else:
            raise ValueError(f"{path}:{number}: unsupported subject {subject!r}")
    return operations


def unquoted(value: str) -> str:
    # csv.reader has already removed the surrounding quotes.
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def datavalue(value: str, datatype: str) -> dict:
    if datatype == "wikibase-item":
        if not re.fullmatch(r"Q\d+", value):
            raise ValueError(f"expected item ID, got {value!r}")
        return {
            "value": {
                "entity-type": "item",
                "numeric-id": int(value[1:]),
                "id": value,
            },
            "type": "wikibase-entityid",
        }
    if datatype == "wikibase-property":
        return {
            "value": {
                "entity-type": "property",
                "numeric-id": int(value[1:]),
                "id": value,
            },
            "type": "wikibase-entityid",
        }
    if datatype == "monolingualtext":
        match = MONOLINGUAL_RE.fullmatch(value)
        if not match:
            raise ValueError(f"expected language:\"text\", got {value!r}")
        return {
            "value": {"language": match.group(1), "text": unquoted(match.group(2))},
            "type": "monolingualtext",
        }
    if datatype in {"string", "external-id", "url", "commonsMedia"}:
        return {"value": unquoted(value), "type": "string"}
    raise ValueError(f"unsupported property datatype {datatype!r}")


def build_data(operation: Operation, datatypes: dict[str, str]) -> dict:
    data: dict = {"labels": {}, "descriptions": {}, "aliases": {}, "claims": {}}
    for number, parts in operation.lines:
        if parts[0] == "CREATE":
            continue
        # A claim is "subject|property|value"; an optional trailing
        # "qualifier-property|qualifier-value" pair adds one qualifier snak,
        # which is how ordered abstract sentences carry their P42 ordinal.
        if len(parts) not in (3, 5):
            raise ValueError(
                f"line {number}: expected three or five pipe-separated fields"
            )
        command, value = parts[1], parts[2]
        term = TERM_RE.fullmatch(command)
        if term:
            if len(parts) != 3:
                raise ValueError(f"line {number}: terms take no qualifier")
            kind, language = term.groups()
            target = {"L": "labels", "D": "descriptions", "A": "aliases"}[kind]
            term_value = {"language": language, "value": unquoted(value)}
            if kind == "A":
                data[target].setdefault(language, []).append(term_value)
            else:
                data[target][language] = term_value
            continue
        if not PROPERTY_RE.fullmatch(command):
            raise ValueError(f"line {number}: unsupported command {command!r}")
        datatype = datatypes.get(command)
        if not datatype:
            raise ValueError(f"line {number}: datatype unavailable for {command}")
        claim = {
            "mainsnak": {
                "snaktype": "value",
                "property": command,
                "datatype": datatype,
                "datavalue": datavalue(value, datatype),
            },
            "type": "statement",
            "rank": "normal",
        }
        if len(parts) == 5:
            qualifier_property, qualifier_value = parts[3], parts[4]
            if not PROPERTY_RE.fullmatch(qualifier_property):
                raise ValueError(
                    f"line {number}: unsupported qualifier {qualifier_property!r}"
                )
            qualifier_datatype = datatypes.get(qualifier_property)
            if not qualifier_datatype:
                raise ValueError(
                    f"line {number}: datatype unavailable for {qualifier_property}"
                )
            claim["qualifiers"] = {
                qualifier_property: [
                    {
                        "snaktype": "value",
                        "property": qualifier_property,
                        "datatype": qualifier_datatype,
                        "datavalue": datavalue(qualifier_value, qualifier_datatype),
                    }
                ]
            }
        data["claims"].setdefault(command, []).append(claim)
    return {key: value for key, value in data.items() if value}


def property_datatypes(client: WikibaseClient, operations: list[Operation]) -> dict[str, str]:
    properties = sorted({
        part
        for operation in operations
        for _, parts in operation.lines
        # index 1 is the mainsnak property; index 3 is an optional qualifier property
        for part in (parts[1:2] + parts[3:4])
        if PROPERTY_RE.fullmatch(part)
    })
    entities = client.entities(properties)
    return {
        prop: entity["datatype"]
        for prop, entity in entities.items()
        if "datatype" in entity
    }


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("completed", []))


def save_state(path: Path, completed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"completed": sorted(completed)}, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--env-file", type=Path, default=Path(".env"),
        help="credential file (default: .env)",
    )
    parser.add_argument("--api")
    parser.add_argument("--apply", action="store_true", help="perform writes")
    parser.add_argument("--summary", default="Import generated site data")
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args(argv)

    load_env(args.env_file)
    api = args.api or os.getenv("WIKIBASE_API", DEFAULT_API)
    username = os.getenv("WIKIBASE_USERNAME")
    password = os.getenv("WIKIBASE_PASSWORD")
    operations = parse(args.input)
    client = WikibaseClient(api, pause=args.pause if args.apply else 0)
    datatypes = property_datatypes(client, operations)
    payloads = [(operation, build_data(operation, datatypes)) for operation in operations]
    print(f"Validated {len(payloads)} entity operation(s)")
    if not args.apply:
        print("Dry run only; pass --apply to write")
        return 0
    if not username or not password:
        parser.error(
            "--apply requires WIKIBASE_USERNAME and WIKIBASE_PASSWORD "
            "in .env or the process environment"
        )
    state_path = args.state or args.input.with_suffix(args.input.suffix + ".state.json")
    completed = load_state(state_path)
    client.login(username, password)
    written = 0
    for operation, data in payloads:
        if operation.key in completed:
            continue
        if args.limit is not None and written >= args.limit:
            break
        response = client.edit_entity(
            data, entity_id=operation.subject, summary=args.summary
        )
        entity_id = response.get("entity", {}).get("id", operation.subject)
        completed.add(operation.key)
        save_state(state_path, completed)
        written += 1
        print(f"Wrote {entity_id}")
    print(f"Completed {written} write(s); state: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
