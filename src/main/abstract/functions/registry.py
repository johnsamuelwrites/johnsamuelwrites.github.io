"""QID-keyed registry for deterministic abstract functions."""

from __future__ import annotations

from collections.abc import Callable

from ..model import FunctionCall
from .text import concatenate_monolingual_text


# This bootstrap key is intentionally not a QID. The binding command replaces
# it with a real local QID after the Wikibase item has been created.
CONCATENATE_BOOTSTRAP_KEY = "bootstrap:concatenate-monolingual-text"


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
