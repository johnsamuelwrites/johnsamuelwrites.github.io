"""Typed values used by the small Q315 abstract-function runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class MonolingualText:
    """Text explicitly associated with one BCP 47 language code."""

    language: str
    text: str

    def __post_init__(self) -> None:
        if not self.language or not self.text:
            raise ValueError("monolingual text requires a language and text")


@dataclass(frozen=True)
class FunctionCall:
    """A typed invocation of a QID-addressed abstract function."""

    function_id: str
    arguments: Mapping[str, object]
