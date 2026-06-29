#!/usr/bin/env python3
"""Move duplicated page CSS into canonical assets owned by Q315.

Groups are declared in ``css-assets.json``. Migration is deliberately strict:
every inline style block in a group must be identical before any file is
changed. Once migrated, ``check`` verifies that every page still references the
canonical asset with the correct relative URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit


HERE = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = HERE.parents[2]
DEFAULT_MANIFEST = HERE / "css-assets.json"

STYLE_BLOCK = re.compile(
    r"(?P<indent>^[ \t]*)<style(?:\s[^>]*)?>(?P<css>.*?)</style>",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CANONICAL_LINK = re.compile(
    r'(?P<indent>^[ \t]*)<link\b'
    r'(?=[^>]*\bdata-q315-css="(?P<group>[^"]+)")'
    r'(?=[^>]*\bhref="(?P<href>[^"]+)")[^>]*/?>',
    flags=re.IGNORECASE | re.MULTILINE,
)


class CSSAssetError(ValueError):
    """Raised when CSS cannot be migrated without ambiguity or data loss."""


@dataclass(frozen=True)
class CSSGroup:
    """A canonical stylesheet and all HTML pages that consume it."""

    identifier: str
    asset: Path
    pages: tuple[Path, ...]
    authoritative_page: Path | None = None


class _AlternateParser(HTMLParser):
    """Collect local ``hreflang`` alternate links without external packages."""

    def __init__(self) -> None:
        super().__init__()
        self.alternates: list[tuple[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        rel = (attributes.get("rel") or "").split()
        language = attributes.get("hreflang")
        href = attributes.get("href")
        if tag.lower() == "link" and "alternate" in rel and language and href:
            self.alternates.append((language, href))


def _repo_relative(path: Path, repo_root: Path, context: str) -> Path:
    try:
        return path.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise CSSAssetError(f"{context}: path escapes the repository") from error


def _collection_groups(raw: dict, repo_root: Path) -> list[CSSGroup]:
    collection_id = raw.get("id", "")
    abstract_root = Path(raw["abstract_root"])
    asset_directory = Path(raw["asset_directory"])
    languages = tuple(raw.get("languages", []))
    if not collection_id or not languages:
        raise CSSAssetError(
            "collection IDs and language lists must be non-empty"
        )

    root_path = repo_root / abstract_root
    if not root_path.is_dir():
        raise CSSAssetError(f"{abstract_root}: abstract collection does not exist")

    groups: list[CSSGroup] = []
    identifiers: set[str] = set()
    for abstract_path in sorted(root_path.rglob("*.html")):
        identifier = (
            abstract_path.parent.name
            if abstract_path.name == "index.html"
            else abstract_path.stem
        )
        if not re.fullmatch(r"Q[0-9]+", identifier):
            raise CSSAssetError(
                f"{abstract_path.relative_to(repo_root)}: cannot derive a QID"
            )
        if identifier in identifiers:
            raise CSSAssetError(
                f"{collection_id}: duplicate abstract page ID {identifier}"
            )

        parser = _AlternateParser()
        parser.feed(abstract_path.read_text(encoding="utf-8"))
        by_language: dict[str, Path] = {}
        for language, href in parser.alternates:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            target = abstract_path.parent / unquote(parsed.path)
            by_language[language] = _repo_relative(
                target, repo_root, str(abstract_path.relative_to(repo_root))
            )
        missing = [language for language in languages if language not in by_language]
        extras = sorted(set(by_language) - set(languages))
        if missing or extras:
            raise CSSAssetError(
                f"{abstract_path.relative_to(repo_root)}: alternate languages "
                f"missing={missing!r}, unexpected={extras!r}"
            )

        abstract_relative = abstract_path.relative_to(repo_root)
        if abstract_path == root_path / "index.html" and raw.get("index_asset"):
            asset = Path(raw["index_asset"])
        else:
            asset = asset_directory / f"{identifier}.css"
        groups.append(
            CSSGroup(
                identifier=identifier,
                asset=asset,
                pages=(
                    abstract_relative,
                    *(by_language[language] for language in languages),
                ),
                authoritative_page=abstract_relative,
            )
        )
        identifiers.add(identifier)
    return groups


def load_groups(
    manifest_path: Path, repo_root: Path = DEFAULT_REPO_ROOT
) -> list[CSSGroup]:
    """Load and minimally validate a CSS asset manifest."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise CSSAssetError(
            f"{manifest_path}: unsupported manifest version "
            f"{data.get('version')!r}"
        )

    groups: list[CSSGroup] = []
    identifiers: set[str] = set()
    for raw in data.get("groups", []):
        identifier = raw.get("id", "")
        if not identifier or identifier in identifiers:
            raise CSSAssetError(
                f"{manifest_path}: group IDs must be non-empty and unique"
            )
        pages = tuple(Path(page) for page in raw.get("pages", []))
        if not pages:
            raise CSSAssetError(f"{identifier}: at least one page is required")
        groups.append(
            CSSGroup(
                identifier=identifier,
                asset=Path(raw["asset"]),
                pages=pages,
                authoritative_page=(
                    Path(raw["authoritative_page"])
                    if raw.get("authoritative_page")
                    else None
                ),
            )
        )
        identifiers.add(identifier)
    for collection in data.get("collections", []):
        for group in _collection_groups(collection, repo_root):
            if group.identifier in identifiers:
                raise CSSAssetError(
                    f"{manifest_path}: duplicate group ID {group.identifier}"
                )
            groups.append(group)
            identifiers.add(group.identifier)
    return groups


def canonical_css(raw_css: str) -> str:
    """Return stable standalone CSS from the contents of an HTML style tag."""
    return textwrap.dedent(raw_css).strip() + "\n"


def stylesheet_href(page: Path, asset: Path) -> str:
    """Return the portable relative URL from an HTML page to an asset."""
    return Path(os.path.relpath(asset, page.parent)).as_posix()


def link_markup(group: CSSGroup, page: Path, indent: str) -> str:
    """Build the canonical stylesheet link for one page."""
    href = stylesheet_href(page, group.asset)
    return (
        f'{indent}<link rel="stylesheet" href="{href}" '
        f'data-q315-css="{group.identifier}" />'
    )


def _page_state(html: str, group: CSSGroup) -> tuple[list[str], list[str]]:
    styles = [canonical_css(match.group("css")) for match in STYLE_BLOCK.finditer(html)]
    links = [
        match.group("href")
        for match in CANONICAL_LINK.finditer(html)
        if match.group("group") == group.identifier
    ]
    return styles, links


def _select_css(
    group: CSSGroup, repo_root: Path, page_html: dict[Path, str]
) -> str:
    asset_path = repo_root / group.asset
    if group.authoritative_page is not None:
        authority_html = page_html[group.authoritative_page]
        authority_styles, _links = _page_state(authority_html, group)
        if len(authority_styles) > 1:
            raise CSSAssetError(
                f"{group.authoritative_page}: expected at most one inline "
                f"style block, found {len(authority_styles)}"
            )
        if authority_styles:
            return authority_styles[0]
        if asset_path.exists():
            return canonical_css(asset_path.read_text(encoding="utf-8"))
        raise CSSAssetError(
            f"{group.identifier}: authoritative page has no inline CSS and "
            "the canonical asset does not exist"
        )

    candidates: list[tuple[Path, str]] = []
    for page, html in page_html.items():
        styles, _links = _page_state(html, group)
        if len(styles) > 1:
            raise CSSAssetError(
                f"{page}: expected at most one inline style block, "
                f"found {len(styles)}"
            )
        if styles:
            candidates.append((page, styles[0]))

    if asset_path.exists():
        candidates.append(
            (group.asset, canonical_css(asset_path.read_text(encoding="utf-8")))
        )
    if not candidates:
        raise CSSAssetError(
            f"{group.identifier}: no inline CSS or existing canonical asset"
        )

    expected = candidates[0][1]
    mismatches = [str(path) for path, css in candidates if css != expected]
    if mismatches:
        paths = ", ".join(mismatches)
        raise CSSAssetError(
            f"{group.identifier}: CSS differs in {paths}; "
            "split the pages into separate groups or reconcile them first"
        )
    return expected


def migrate_group(group: CSSGroup, repo_root: Path) -> int:
    """Extract a group's common CSS and rewrite every page atomically."""
    page_html: dict[Path, str] = {}
    for relative_page in group.pages:
        page = repo_root / relative_page
        if not page.is_file():
            raise CSSAssetError(f"{relative_page}: page does not exist")
        page_html[relative_page] = page.read_text(encoding="utf-8")

    css = _select_css(group, repo_root, page_html)
    updated_pages: dict[Path, str] = {}
    for relative_page, html in page_html.items():
        styles, links = _page_state(html, group)
        if styles:
            match = STYLE_BLOCK.search(html)
            assert match is not None
            updated = STYLE_BLOCK.sub(
                link_markup(group, relative_page, match.group("indent")),
                html,
                count=1,
            )
        elif len(links) == 1:
            link = next(
                match
                for match in CANONICAL_LINK.finditer(html)
                if match.group("group") == group.identifier
            )
            updated = (
                html[: link.start()]
                + link_markup(group, relative_page, link.group("indent"))
                + html[link.end() :]
            )
        else:
            raise CSSAssetError(
                f"{relative_page}: expected one inline style block or one "
                f"canonical link, found {len(links)} links"
            )
        updated_pages[relative_page] = updated

    changed = 0
    asset_path = repo_root / group.asset
    existing_css = (
        canonical_css(asset_path.read_text(encoding="utf-8"))
        if asset_path.exists()
        else None
    )
    if existing_css != css:
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_text(css, encoding="utf-8")
        changed += 1

    for relative_page, updated in updated_pages.items():
        path = repo_root / relative_page
        if updated != page_html[relative_page]:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def check_group(group: CSSGroup, repo_root: Path) -> list[str]:
    """Return validation errors for a migrated CSS group."""
    errors: list[str] = []
    asset = repo_root / group.asset
    if not asset.is_file():
        errors.append(f"{group.asset}: canonical asset does not exist")
    elif not asset.read_text(encoding="utf-8").strip():
        errors.append(f"{group.asset}: canonical asset is empty")

    for relative_page in group.pages:
        page = repo_root / relative_page
        if not page.is_file():
            errors.append(f"{relative_page}: page does not exist")
            continue
        styles, links = _page_state(page.read_text(encoding="utf-8"), group)
        expected = stylesheet_href(relative_page, group.asset)
        if styles:
            errors.append(f"{relative_page}: still contains inline CSS")
        if links != [expected]:
            errors.append(
                f"{relative_page}: expected exactly one {group.identifier} "
                f'link to "{expected}", found {links!r}'
            )
    return errors


def selected_groups(
    groups: Sequence[CSSGroup], identifiers: Sequence[str]
) -> list[CSSGroup]:
    """Select requested groups while reporting unknown IDs."""
    if not identifiers:
        return list(groups)
    by_id = {group.identifier: group for group in groups}
    unknown = sorted(set(identifiers) - by_id.keys())
    if unknown:
        raise CSSAssetError(f"unknown CSS group(s): {', '.join(unknown)}")
    return [by_id[identifier] for identifier in identifiers]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="repository root (defaults to the root containing src/)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="CSS asset manifest",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("migrate", "check"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--group",
            action="append",
            default=[],
            help="group ID to process; repeat as needed (default: all)",
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        groups = selected_groups(
            load_groups(args.manifest, repo_root), args.group
        )
        if args.command == "migrate":
            changed = sum(migrate_group(group, repo_root) for group in groups)
            print(f"Migrated {len(groups)} CSS group(s); changed {changed} file(s)")
            return 0

        errors = [
            error
            for group in groups
            for error in check_group(group, repo_root)
        ]
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Validated {len(groups)} canonical CSS group(s)")
        return 0
    except CSSAssetError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
