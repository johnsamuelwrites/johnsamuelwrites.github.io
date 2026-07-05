#!/usr/bin/env python3
"""Validate the machine-readable contract of canonical Q315 HTML."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence


QUALIFIED_QID = re.compile(r"^(?:local|wikidata):Q[1-9][0-9]*$")


class AbstractHTMLValidator(HTMLParser):
    """Validate abstract metadata and the small function-call vocabulary."""

    def __init__(self, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.errors: list[str] = []
        self.seen_html = False
        self.call_depth = 0

    def error(self, message: str) -> None:
        line, column = self.getpos()
        self.errors.append(f"{self.source}:{line}:{column + 1}: {message}")

    def qualified_qid(self, value: str | None, attribute: str) -> None:
        if value is None or not QUALIFIED_QID.fullmatch(value):
            self.error(
                f'{attribute} must be a qualified "local:Q…" or '
                f'"wikidata:Q…" reference, found {value!r}'
            )

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "html":
            if self.seen_html:
                self.error("document contains more than one html element")
            self.seen_html = True
            if attributes.get("lang") != "zxx":
                self.error('canonical abstract HTML must use lang="zxx"')
            self.qualified_qid(
                attributes.get("data-abstract-page"), "data-abstract-page"
            )
            if attributes.get("data-abstract-version") != "1":
                self.error('data-abstract-version must currently be "1"')
        elif tag == "q-call":
            self.qualified_qid(attributes.get("data-function"), "data-function")
            self.call_depth += 1
        elif tag == "q-arg":
            if self.call_depth == 0:
                self.error("q-arg must be contained in q-call")
            if not attributes.get("data-name"):
                self.error("q-arg requires a non-empty data-name")

        for attribute in ("data-entity", "data-content"):
            if attribute in attributes:
                self.qualified_qid(attributes[attribute], attribute)

    def handle_endtag(self, tag: str) -> None:
        if tag == "q-call":
            if self.call_depth == 0:
                self.error("closing q-call has no matching start tag")
            else:
                self.call_depth -= 1

    def finish(self) -> list[str]:
        if not self.seen_html:
            self.errors.append(f"{self.source}: missing html element")
        if self.call_depth:
            self.errors.append(f"{self.source}: unclosed q-call element")
        return self.errors


def validate(path: Path) -> list[str]:
    validator = AbstractHTMLValidator(path)
    validator.feed(path.read_text(encoding="utf-8"))
    validator.close()
    return validator.finish()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="HTML files or directories to search recursively",
    )
    return parser


def html_documents(paths: Sequence[Path]) -> tuple[list[Path], list[str]]:
    documents: list[Path] = []
    errors: list[str] = []
    for path in paths:
        if path.is_dir():
            documents.extend(sorted(path.rglob("*.html")))
        elif path.is_file():
            documents.append(path)
        else:
            errors.append(f"{path}: file or directory does not exist")
    return documents, errors


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    documents, errors = html_documents(args.paths)
    for path in documents:
        errors.extend(validate(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {len(documents)} abstract HTML document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
