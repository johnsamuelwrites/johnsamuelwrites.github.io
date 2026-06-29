"""Language-aware text constructors."""

from __future__ import annotations

from collections.abc import Sequence

from ..model import MonolingualText


def concatenate_monolingual_text(
    *,
    parts: Sequence[MonolingualText],
    language: str,
    separator: str = " ",
) -> MonolingualText:
    """Join ordered text parts while preserving their language type."""
    if not parts:
        raise ValueError("concatenate requires at least one part")
    mismatched = [part.language for part in parts if part.language != language]
    if mismatched:
        raise ValueError(
            "all concatenate parts must match the requested language "
            f"{language!r}; found {mismatched!r}"
        )
    return MonolingualText(
        language=language,
        text=separator.join(part.text for part in parts),
    )
