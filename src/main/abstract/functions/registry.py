"""QID-keyed registry for deterministic abstract functions."""

from __future__ import annotations

from collections.abc import Callable

from ..model import FunctionCall
from .text import compose_ordered_paragraph, concatenate_monolingual_text


# These bootstrap keys are intentionally not QIDs. The binding command replaces
# each with a real local QID after the Wikibase function item has been created.
CONCATENATE_BOOTSTRAP_KEY = "bootstrap:concatenate-monolingual-text"
COMPOSE_PARAGRAPH_BOOTSTRAP_KEY = "bootstrap:compose-ordered-paragraph"


class FunctionRegistry:
    """Resolve and evaluate explicitly registered, side-effect-free functions."""

    def __init__(self) -> None:
        self._functions: dict[str, Callable[..., object]] = {}

    def register(self, identifier: str, function: Callable[..., object]) -> None:
        if identifier in self._functions:
            raise ValueError(f"function already registered: {identifier}")
        self._functions[identifier] = function

    def evaluate(self, call: FunctionCall) -> object:
        try:
            function = self._functions[call.function_id]
        except KeyError as error:
            raise ValueError(f"unknown abstract function: {call.function_id}") from error
        return function(**call.arguments)


default_registry = FunctionRegistry()
default_registry.register(
    CONCATENATE_BOOTSTRAP_KEY,
    concatenate_monolingual_text,
)
default_registry.register(
    COMPOSE_PARAGRAPH_BOOTSTRAP_KEY,
    compose_ordered_paragraph,
)
