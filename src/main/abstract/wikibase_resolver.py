"""Resolve a typed abstract paragraph from a pinned Wikibase snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import FunctionCall, MonolingualText


@dataclass(frozen=True)
class ResolvedParagraph:
    item: str
    function: str
    parts: tuple[tuple[int, str, dict[str, MonolingualText]], ...]


def _item_value(statement: dict) -> str:
    return statement["mainsnak"]["datavalue"]["value"]["id"]


def _has_item(entity: dict, prop: str, item: str) -> bool:
    return any(_item_value(statement) == item for statement in entity["claims"].get(prop, []))


class WikibaseResolver:
    def __init__(self, snapshot: dict) -> None:
        if snapshot.get("schema_version") != 1:
            raise ValueError("unsupported Wikibase snapshot schema")
        self.entities = snapshot["entities"]

    @classmethod
    def from_path(cls, path: Path) -> "WikibaseResolver":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def paragraph(self, item: str = "Q3838") -> ResolvedParagraph:
        paragraph = self.entities[item]
        if not _has_item(paragraph, "P8", "Q3835"):
            raise ValueError(f"{item} is not an abstract paragraph")
        constructors = paragraph["claims"].get("P41", [])
        if len(constructors) != 1:
            raise ValueError(f"{item} must have exactly one constructor")
        function = _item_value(constructors[0])
        if not _has_item(self.entities[function], "P8", "Q3834"):
            raise ValueError(f"{function} is not an abstract function")

        parts = []
        for sentence_id, entity in self.entities.items():
            if not sentence_id.startswith("Q") or not _has_item(entity, "P8", "Q3836"):
                continue
            memberships = [
                statement
                for statement in entity["claims"].get("P21", [])
                if _item_value(statement) == item
            ]
            for membership in memberships:
                ordinals = membership.get("qualifiers", {}).get("P42", [])
                if len(ordinals) != 1:
                    raise ValueError(f"{sentence_id} requires one P42 ordinal")
                ordinal = int(ordinals[0]["datavalue"]["value"])
                values: dict[str, MonolingualText] = {}
                for statement in entity["claims"].get("P40", []):
                    value = statement["mainsnak"]["datavalue"]["value"]
                    language = value["language"]
                    if language in values:
                        raise ValueError(
                            f"{sentence_id} has duplicate P40 language {language}"
                        )
                    values[language] = MonolingualText(language, value["text"])
                parts.append((ordinal, sentence_id, values))
        parts.sort(key=lambda part: part[0])
        if [part[0] for part in parts] != list(range(1, len(parts) + 1)):
            raise ValueError(f"{item} P42 ordinals are not contiguous")
        return ResolvedParagraph(item, function, tuple(parts))

    def call(self, paragraph: ResolvedParagraph, language: str) -> FunctionCall:
        values = []
        for _ordinal, sentence, translations in paragraph.parts:
            if language not in translations:
                raise ValueError(f"{sentence} has no P40 value for {language}")
            values.append(translations[language])
        return FunctionCall(
            function_id=f"local:{paragraph.function}",
            arguments={"parts": values, "language": language},
        )
