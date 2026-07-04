#!/usr/bin/env python3
"""Discover legacy articles and their Q315 migration/target relationships."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.prepare_travel_content import LANGUAGES

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "content-migration-registry.csv"
QUALIFIED_QID = re.compile(r"^(?:local|wikidata):(Q[1-9][0-9]*)$")


class PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.abstract_qid = ""
        self.alternates: dict[str, str] = {}
        self.generator = ""

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        if tag == "html":
            match = QUALIFIED_QID.fullmatch(values.get("data-abstract-page") or "")
            if match:
                self.abstract_qid = match.group(1)
        elif tag == "link" and values.get("rel") == "alternate":
            language = values.get("hreflang")
            href = values.get("href")
            if language in LANGUAGES and href:
                self.alternates[language] = href
        elif tag == "meta" and values.get("name") == "generator":
            self.generator = values.get("content") or ""


@dataclass(frozen=True)
class PageMetadata:
    path: Path
    qid: str
    alternates: dict[str, Path]
    generated: bool
    digest: str


def repository_path(repo_root: Path, source: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        return None
    candidate = (source.parent / unquote(parsed.path)).resolve()
    try:
        return candidate.relative_to(repo_root)
    except ValueError:
        return None


def read_metadata(repo_root: Path, relative: Path) -> PageMetadata:
    source = repo_root / relative
    raw = source.read_bytes()
    parser = PageMetadataParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    alternates = {
        language: target
        for language, href in parser.alternates.items()
        if (target := repository_path(repo_root, source, href)) is not None
    }
    return PageMetadata(
        path=relative,
        qid=parser.abstract_qid,
        alternates=alternates,
        generated=parser.generator == "Q315 renderer",
        digest=hashlib.sha256(raw).hexdigest(),
    )


def html_pages(repo_root: Path, root: str) -> list[Path]:
    directory = repo_root / root
    if not directory.is_dir():
        return []
    return sorted(path.relative_to(repo_root) for path in directory.rglob("*.html"))


def abstract_index(repo_root: Path) -> tuple[dict[Path, PageMetadata], dict[Path, Path]]:
    pages: dict[Path, PageMetadata] = {}
    by_rendered_path: dict[Path, Path] = {}
    for relative in html_pages(repo_root, "Q315"):
        metadata = read_metadata(repo_root, relative)
        if not metadata.qid:
            continue
        pages[relative] = metadata
        for target in metadata.alternates.values():
            by_rendered_path.setdefault(target, relative)
    return pages, by_rendered_path


def abstract_sources(repo_root: Path, page: str = "") -> list[tuple[str, Path]]:
    """Return ``(page_qid, abstract_path)`` for every discovered abstract page.

    The set of abstract pages is derived from the repository itself: any page
    under ``Q315/`` that declares ``data-abstract-page``. This replaces the
    hand-written page-list CSVs the pilots used, so newly authored abstract
    pages are picked up automatically. An optional ``page`` QID scopes the
    result to a single abstract page.
    """
    pages, _ = abstract_index(repo_root)
    sources = sorted(
        (metadata.qid, relative)
        for relative, metadata in pages.items()
    )
    if page:
        sources = [row for row in sources if row[0] == page]
        if not sources:
            raise ValueError(f"no abstract page declares QID {page}")
    return sources


def discover(repo_root: Path) -> list[dict[str, str]]:
    abstract_pages, abstract_by_target = abstract_index(repo_root)
    legacy_paths = set(html_pages(repo_root, "en")) | set(html_pages(repo_root, "fr"))
    metadata = {path: read_metadata(repo_root, path) for path in sorted(legacy_paths)}
    reverse_alternates: dict[Path, set[Path]] = {}
    for candidate, candidate_metadata in metadata.items():
        for target in candidate_metadata.alternates.values():
            reverse_alternates.setdefault(target, set()).add(candidate)
    visited: set[Path] = set()
    rows: list[dict[str, str]] = []

    for path in sorted(legacy_paths):
        if path in visited:
            continue
        page = metadata[path]
        group = {path}
        abstract_path_for_page = abstract_by_target.get(path)
        if abstract_path_for_page:
            group.update(
                target
                for language, target in abstract_pages[
                    abstract_path_for_page
                ].alternates.items()
                if language in {"en", "fr"} and target in legacy_paths
            )
        for language in ("en", "fr"):
            target = page.alternates.get(language)
            if target in legacy_paths:
                group.add(target)
        # A reverse alternate is also valid when only one side declares it.
        group.update(reverse_alternates.get(path, set()))
        visited.update(group)

        by_language = {
            member.parts[0]: member
            for member in group
            if member.parts and member.parts[0] in {"en", "fr"}
        }
        abstract_candidates = {
            abstract_by_target[member]
            for member in group
            if member in abstract_by_target
        }
        abstract_path = (
            sorted(abstract_candidates)[0] if len(abstract_candidates) == 1 else None
        )
        abstract = abstract_pages.get(abstract_path) if abstract_path else None

        targets: dict[str, Path] = {}
        if abstract:
            targets.update(abstract.alternates)
        else:
            for member in group:
                targets.update(metadata[member].alternates)
        targets.update(
            {
                language: member
                for language, member in by_language.items()
            }
        )

        rendered_metadata = {
            language: (
                metadata[target]
                if target in metadata
                else read_metadata(repo_root, target)
            )
            for language, target in targets.items()
            if (repo_root / target).is_file()
        }
        generated_languages = [
            language for language, item in rendered_metadata.items() if item.generated
        ]
        if generated_languages and len(generated_languages) != len(rendered_metadata):
            ownership = "mixed-error"
        elif generated_languages:
            ownership = "abstract"
        else:
            ownership = "legacy"

        if len(abstract_candidates) > 1:
            state = "identity-conflict"
        elif abstract and ownership == "abstract":
            state = "generated-owner"
        elif abstract:
            state = "abstract-authored"
        elif "en" in by_language and "fr" in by_language:
            state = "discovered"
        else:
            state = "unpaired"

        use_legacy_sources = ownership != "abstract"
        row = {
            "page_qid": abstract.qid if abstract else "",
            "abstract_path": abstract_path.as_posix() if abstract_path else "",
            "en_source": (
                by_language["en"].as_posix()
                if use_legacy_sources and "en" in by_language
                else ""
            ),
            "fr_source": (
                by_language["fr"].as_posix()
                if use_legacy_sources and "fr" in by_language
                else ""
            ),
            "migration_state": state,
            "render_ownership": ownership,
            "en_source_hash": (
                metadata[by_language["en"]].digest
                if use_legacy_sources and "en" in by_language
                else ""
            ),
            "fr_source_hash": (
                metadata[by_language["fr"]].digest
                if use_legacy_sources and "fr" in by_language
                else ""
            ),
        }
        row.update(
            {
                f"target_{language}": (
                    targets[language].as_posix() if language in targets else ""
                )
                for language in LANGUAGES
            }
        )
        rows.append(row)
    return rows


def write_registry(path: Path, rows: list[dict[str, str]]) -> None:
    fields = (
        "page_qid", "abstract_path", "en_source", "fr_source",
        *(f"target_{language}" for language in LANGUAGES),
        "migration_state", "render_ownership", "en_source_hash", "fr_source_hash",
    )
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = discover(args.repo_root.resolve())
    write_registry(args.output, rows)
    counts: dict[str, int] = {}
    for row in rows:
        state = row["migration_state"]
        counts[state] = counts.get(state, 0) + 1
    print(f"Discovered {len(rows)} logical article candidates")
    for state in sorted(counts):
        print(f"{state}: {counts[state]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
