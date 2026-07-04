"""Language-aware text constructors."""

from __future__ import annotations

from collections.abc import Sequence

from ..model import MonolingualText


# Inter-sentence spacing inside a paragraph is a property of the language, not
# of the caller. Sentence-terminal punctuation already lives inside each part,
# so most scripts join with a single space; languages written without word or
# sentence spacing join with none. The map holds only the exceptions; every
# other language falls back to a single space.
SENTENCE_SPACING = {
    "ja": "",
    "zh": "",
    "ko": "",
    "th": "",
}
DEFAULT_SENTENCE_SPACING = " "


def _require_language(parts: Sequence[MonolingualText], language: str) -> None:
    mismatched = [part.language for part in parts if part.language != language]
    if mismatched:
        raise ValueError(
            "all parts must match the requested language "
            f"{language!r}; found {mismatched!r}"
        )


def concatenate_monolingual_text(
    *,
    parts: Sequence[MonolingualText],
    language: str,
    separator: str = " ",
) -> MonolingualText:
    """Join ordered text parts while preserving their language type."""
    if not parts:
        raise ValueError("concatenate requires at least one part")
    _require_language(parts, language)
    return MonolingualText(
        language=language,
        text=separator.join(part.text for part in parts),
    )


def compose_ordered_paragraph(
    *,
    parts: Sequence[MonolingualText],
    language: str,
) -> MonolingualText:
    """Join ordered sentences into a paragraph with locale-aware spacing.

    Unlike :func:`concatenate_monolingual_text`, the separator is not a caller
    argument: it is the inter-sentence spacing the requested language uses, so
    the same abstract paragraph renders with correct spacing in every language
    without the page having to specify it. Each part is expected to be a
    complete sentence carrying its own terminal punctuation.
    """
    if not parts:
        raise ValueError("a paragraph requires at least one sentence")
    _require_language(parts, language)
    spacing = SENTENCE_SPACING.get(language, DEFAULT_SENTENCE_SPACING)
    return MonolingualText(
        language=language,
        text=spacing.join(part.text for part in parts),
    )
