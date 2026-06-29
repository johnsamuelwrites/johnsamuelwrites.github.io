#!/usr/bin/env python3
"""Bind travel content QIDs from the manifest into Q315 abstract HTML pages."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_MANIFEST, DEFAULT_REPO_ROOT, load_groups


DEFAULT_TRAVEL_MANIFEST = HERE / "travel-content-manifest.csv"
DATA_CONTENT = re.compile(r'\sdata-content="(?P<value>[^"]*)"')


@dataclass(frozen=True)
class Binding:
    qid: str
    tag: str
    class_signature: str
    role: str
    occurrence: int

    @property
    def key(self) -> tuple[str, str, str, int]:
        return (self.tag, self.class_signature, self.role, self.occurrence)


class BindingError(ValueError):
    """Raised when a manifest binding cannot be safely applied."""


class StartTagBinder(HTMLParser):
    """Locate manifest target start tags and prepare data-content insertions."""

    def __init__(
        self,
        source: str,
        page: str,
        bindings: dict[tuple[str, str, str, int], str],
    ) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.page = page
        self.bindings = bindings
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.cursor = 0
        self.insertions: list[tuple[int, str]] = []
        self.replacements: list[tuple[int, int, str]] = []
        self.content_replacements: list[tuple[int, int, str]] = []
        self.targets: list[tuple[str, int, str]] = []
        self.matched: set[tuple[str, str, str, int]] = set()
        self.errors: list[str] = []
        self.owned_values = {f"local:{qid}" for qid in bindings.values()}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if not self.targets or self.targets[-1][0] != tag:
            return

        match = re.search(rf"</\s*{re.escape(tag)}\s*>", self.source[self.cursor :], re.I)
        if not match:
            self.errors.append(f"{self.page}: cannot locate end tag for {tag}")
            return
        end_start = self.cursor + match.start()
        end_end = self.cursor + match.end()
        self.cursor = end_end

        _, content_start, qid = self.targets.pop()
        self.content_replacements.append((content_start, end_start, qid))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_tag(tag, attrs)

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        base = (
            tag,
            ".".join(sorted((values.get("class") or "").split())),
            values.get("role") or "",
        )
        index = self.counts[base]
        self.counts[base] += 1
        key = (*base, index)
        qid = self.bindings.get(key)

        start_tag = self.get_starttag_text()
        if not start_tag:
            self.errors.append(f"{self.page}: cannot recover start tag for {key}")
            return
        start = self.source.find(start_tag, self.cursor)
        if start < 0:
            self.errors.append(f"{self.page}: cannot locate start tag for {key}")
            return
        self.cursor = start + len(start_tag)

        existing = DATA_CONTENT.search(start_tag)
        if not qid:
            if existing and existing.group("value") in self.owned_values:
                self.replacements.append(
                    (
                        start + existing.start(),
                        start + existing.end(),
                        "",
                    )
                )
            return

        expected = f"local:{qid}"
        content_start = start + len(start_tag)
        if existing:
            if existing.group("value") != expected:
                if existing.group("value") in self.owned_values:
                    self.replacements.append(
                        (
                            start + existing.start(),
                            start + existing.end(),
                            f' data-content="{expected}"',
                        )
                    )
                else:
                    self.errors.append(
                        f"{self.page}: {key} has data-content={existing.group('value')!r}, "
                        f"expected {expected!r}"
                    )
            self.matched.add(key)
            self.targets.append((tag, content_start, qid))
            return

        insert_at = start + len(start_tag) - (2 if start_tag.endswith("/>") else 1)
        self.insertions.append((insert_at, f' data-content="{expected}"'))
        self.matched.add(key)
        self.targets.append((tag, content_start, qid))

    def close(self) -> None:
        super().close()
        missing = sorted(set(self.bindings) - self.matched)
        for key in missing:
            if self.content_replacements:
                continue
            self.errors.append(f"{self.page}: did not find manifest target {key}")


def load_manifest(path: Path) -> dict[str, dict[tuple[str, str, str, int], str]]:
    by_page: dict[str, dict[tuple[str, str, str, int], str]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            page = row["page"].strip()
            qid = row["token"].strip()
            binding = Binding(
                qid=qid,
                tag=row["tag"].strip(),
                class_signature=row["class"].strip(),
                role=row["role"].strip(),
                occurrence=int(row["occurrence"]),
            )
            previous = by_page[page].get(binding.key)
            if previous and previous != qid:
                raise BindingError(
                    f"{path}: {page} {binding.key} maps to both {previous} and {qid}"
                )
            by_page[page][binding.key] = qid
    return dict(by_page)


def abstract_pages(repo_root: Path) -> dict[str, Path]:
    return {
        group.identifier: group.authoritative_page
        for group in load_groups(DEFAULT_MANIFEST, repo_root)
        if group.authoritative_page
    }


def bind_page(
    repo_root: Path,
    page: str,
    relative: Path,
    bindings: dict[tuple[str, str, str, int], str],
) -> tuple[Path, str, list[str]]:
    path = repo_root / relative
    source = path.read_text(encoding="utf-8")
    parser = StartTagBinder(source, page, bindings)
    parser.feed(source)
    parser.close()
    if parser.errors:
        return relative, source, parser.errors

    output = source
    content_edits = outer_content_replacements(parser.content_replacements)
    edits = [
        (*replacement,)
        for replacement in parser.replacements
        if not inside_any(replacement[0], replacement[1], content_edits)
    ]
    edits.extend(
        (position, position, text)
        for position, text in parser.insertions
        if not inside_any(position, position, content_edits)
    )
    edits.extend(content_edits)
    for start, end, text in sorted(edits, reverse=True):
        output = output[:start] + text + output[end:]
    return relative, output, []


def outer_content_replacements(
    replacements: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    outer: list[tuple[int, int, str]] = []
    for replacement in sorted(replacements, key=lambda item: (item[0], -item[1])):
        start, end, _ = replacement
        if any(parent_start <= start and end <= parent_end for parent_start, parent_end, _ in outer):
            continue
        outer.append(replacement)
    return outer


def inside_any(
    start: int,
    end: int,
    containers: list[tuple[int, int, str]],
) -> bool:
    return any(container_start <= start and end <= container_end for container_start, container_end, _ in containers)


def bind(
    repo_root: Path,
    manifest: Path,
    check: bool = False,
) -> tuple[int, int, list[str]]:
    bindings_by_page = load_manifest(manifest)
    known_pages = abstract_pages(repo_root)
    errors: list[str] = []
    unknown_pages = sorted(set(bindings_by_page) - set(known_pages))
    if unknown_pages:
        errors.extend(f"{page}: page not found in Q3062 CSS manifest" for page in unknown_pages)

    changed = 0
    visited = 0
    for page in sorted(bindings_by_page):
        if page in unknown_pages:
            continue
        relative, output, page_errors = bind_page(
            repo_root,
            page,
            known_pages[page],
            bindings_by_page[page],
        )
        visited += 1
        if page_errors:
            errors.extend(page_errors)
            continue
        path = repo_root / relative
        source = path.read_text(encoding="utf-8")
        if source != output:
            changed += 1
            if check:
                errors.append(f"{relative}: manifest bindings are not current")
            else:
                path.write_text(output, encoding="utf-8")

    return visited, changed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_TRAVEL_MANIFEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        visited, changed, errors = bind(
            repo_root=args.repo_root.resolve(),
            manifest=args.manifest,
            check=args.check,
        )
    except BindingError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    action = "Validated" if args.check else "Bound"
    print(f"{action} {visited} Q315 travel page(s); {changed} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
