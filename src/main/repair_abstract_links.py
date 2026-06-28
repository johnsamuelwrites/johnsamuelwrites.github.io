#!/usr/bin/env python3
"""Rebase links in generated Q315 pages against their concrete source pages."""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from content_components_quickstatements import page_sets
from paths import REPO_ROOT


ATTRIBUTE = re.compile(r'(?P<name>href|src)="(?P<value>[^"]+)"')


def mappings() -> tuple[dict[Path, Path], dict[Path, Path]]:
    target_to_source: dict[Path, Path] = {}
    source_to_target: dict[Path, Path] = {}
    for _item, target, languages in page_sets():
        target = target.resolve()
        source = languages["en"].resolve()
        target_to_source[target] = source
        source_to_target[source] = target
    with (REPO_ROOT / "remaining-abstract-pages.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            if row["language"] != "en":
                continue
            target = (REPO_ROOT / row["abstract_path"]).resolve()
            concrete = (REPO_ROOT / row["path"]).resolve()
            target_to_source[target] = concrete
            source_to_target[concrete] = target
    return target_to_source, source_to_target


def local_path(value: str) -> str | None:
    parts = urlsplit(value)
    if (
        parts.scheme
        or parts.netloc
        or value.startswith(("#", "//", "mailto:", "tel:", "data:"))
        or not parts.path
    ):
        return None
    return unquote(parts.path)


def repair_page(
    target: Path,
    source: Path,
    source_to_target: dict[Path, Path],
) -> int:
    html = target.read_text(encoding="utf-8")
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        value = match.group("value")
        path = local_path(value)
        if path is None:
            return match.group(0)
        current = (target.parent / path).resolve()
        if current.exists():
            return match.group(0)
        concrete = (source.parent / path).resolve()
        if not concrete.exists():
            return match.group(0)
        destination = source_to_target.get(concrete, concrete)
        relative = Path(os.path.relpath(destination, target.parent)).as_posix()
        parts = urlsplit(value)
        if parts.query:
            relative += f"?{parts.query}"
        if parts.fragment:
            relative += f"#{parts.fragment}"
        changed += 1
        return f'{match.group("name")}="{relative}"'

    updated = ATTRIBUTE.sub(replace, html)
    if updated != html:
        target.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    target_to_source, source_to_target = mappings()
    changed = 0
    missing_targets: list[Path] = []
    for target, source in target_to_source.items():
        if not target.is_file():
            missing_targets.append(target)
            continue
        changed += repair_page(target, source, source_to_target)
    print(
        f"Rebased {changed} links in {len(target_to_source)} abstract pages; "
        f"{len(missing_targets)} manifest targets missing"
    )
    return 1 if missing_targets else 0


if __name__ == "__main__":
    raise SystemExit(main())
