#!/usr/bin/env python3
"""Guard rendered Q315 pages against common translation/link regressions."""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_travel_content import LANGUAGES
from abstract.render_page import COMPOSED_ITEMTYPES
from abstract.verify_content_roundtrip import normalize_text

PROSE_CONTEXT_CLASSES = frozenset(
    {
        "hero-subtitle",
        "intro-text",
        "section-intro",
        "subtitle",
        "description",
        "hero-description",
        "section-subtitle",
        "nav-subtitle",
    }
)
PROSE_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "across",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "that",
        "the",
        "through",
        "to",
        "with",
    }
)


@dataclass(frozen=True)
class BoundSlot:
    qid: str
    tag: str
    css_class: str
    parent_classes: tuple[str, ...]


class AbstractBindingParser(HTMLParser):
    """Collect bound atomic slots and their nearby class context."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, str]] = []
        self.slots: list[BoundSlot] = []

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        css_class = ".".join(sorted((values.get("class") or "").split()))
        for attr in ("data-content", "data-entity"):
            value = values.get(attr) or ""
            if value.startswith("local:"):
                self.slots.append(
                    BoundSlot(
                        qid=value.removeprefix("local:"),
                        tag=tag,
                        css_class=css_class,
                        parent_classes=tuple(cls for _, cls in self.stack if cls),
                    )
                )
        self.stack.append((tag, css_class))

    def handle_endtag(self, tag) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def abstract_slots(path: Path) -> list[BoundSlot]:
    parser = AbstractBindingParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.slots


def _class_tokens(value: str) -> set[str]:
    return set(value.split(".")) if value else set()


def is_prose_slot(slot: BoundSlot, label: str) -> bool:
    """Return true for bound text that should normally be translated.

    Many Q315 slots intentionally keep canonical names, titles, venues, and
    identifiers identical across languages. This predicate stays narrow: it only
    guards prose-like labels in paragraph/subtitle/intro contexts.
    """
    text = normalize_text(label)
    if not text or re.fullmatch(r"Q[1-9][0-9]*", text):
        return False
    words = re.findall(r"[A-Za-z]+", text.lower())
    if len(words) < 2:
        return False
    if not re.search(r"[a-z]", text):
        return False
    context = _class_tokens(slot.css_class)
    for parent in slot.parent_classes:
        context.update(_class_tokens(parent))
    if not context.intersection(PROSE_CONTEXT_CLASSES):
        return False
    stopword_count = sum(1 for word in words if word in PROSE_STOPWORDS)
    if len(words) <= 3:
        return stopword_count >= 1
    if stopword_count < 2:
        return False
    return True


def untranslated_label_errors(
    repo_root: Path, data_dir: Path, page: str = ""
) -> list[str]:
    labels = load_labels(data_dir)
    errors: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    rows = [
        row
        for row in discover(repo_root)
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not rows:
        raise ValueError(f"no abstract page declares QID {page}")
    for row in rows:
        abstract_path = repo_root / row["abstract_path"]
        for slot in abstract_slots(abstract_path):
            label = labels.get(slot.qid, {})
            itemtype = (label.get("itemtype") or "").strip()
            if itemtype in COMPOSED_ITEMTYPES:
                continue
            english = (label.get("en") or "").strip()
            if not is_prose_slot(slot, english):
                continue
            for language in LANGUAGES:
                if language == "en" or not row.get(f"target_{language}"):
                    continue
                localized = (label.get(language) or "").strip()
                if normalize_text(localized) == normalize_text(english):
                    key = (row["page_qid"], slot.qid, language, english)
                    if key in seen:
                        continue
                    seen.add(key)
                    errors.append(
                        f"{row['abstract_path']}: {slot.qid} has untranslated "
                        f"{language} prose label matching English: {english!r}"
                    )
    return errors


Q315_OWNED_ELEMENT = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)\b[^>]*"
    r'data-q315-source="local:(?P<qid>Q[1-9][0-9]*)"[^>]*>'
    r"(?P<body>.*?)</(?P=tag)>",
    flags=re.DOTALL,
)
ANCHOR = re.compile(r"<a\b[^>]*>.*?</a>", flags=re.DOTALL | re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")


def visible_text(markup: str) -> str:
    return normalize_text(html.unescape(TAG.sub("", markup)))


def bare_parentheses_errors(repo_root: Path, page: str = "") -> list[str]:
    errors: list[str] = []
    rows = [
        row
        for row in discover(repo_root)
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not rows:
        raise ValueError(f"no abstract page declares QID {page}")
    for row in rows:
        for language in LANGUAGES:
            relative = row.get(f"target_{language}") or ""
            if not relative:
                continue
            path = repo_root / relative
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8")
            for match in Q315_OWNED_ELEMENT.finditer(source):
                body_without_anchors = ANCHOR.sub("LINK", match.group("body"))
                if "()" in visible_text(body_without_anchors):
                    errors.append(
                        f"{relative}: {match.group('qid')} contains bare () "
                        "inside Q315-owned rendered content"
                    )
    return errors


def validate(repo_root: Path, data_dir: Path, page: str = "") -> list[str]:
    return untranslated_label_errors(repo_root, data_dir, page) + bare_parentheses_errors(
        repo_root, page
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--page", default="", help="restrict validation to one page QID")
    args = parser.parse_args(argv)
    try:
        errors = validate(args.repo_root.resolve(), args.data_dir.resolve(), args.page)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"ERROR: {error}")
    scope = f" for {args.page}" if args.page else ""
    print(f"Rendered Q315 guard{scope}: {len(errors)} issue(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
