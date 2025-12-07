#
# SPDX-FileCopyrightText: 2025 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import os
import argparse
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, Set, List, Iterable


class LinkExtractor(HTMLParser):
    """Extract hrefs from <a> tags in an HTML string."""

    def __init__(self):
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value is not None:
                self.links.append(value)


def find_html_files(
    root: Path,
    exclude_dirs: Iterable[str] = (),
    exclude_files: Iterable[str] = (),
) -> List[Path]:
    """
    Recursively find all .html files under root.

    exclude_dirs: directory names or root-relative paths to skip.
    exclude_files: filenames or root-relative paths of files to skip.
    """
    # Normalize excludes for dirs
    exclude_dir_names = set()
    exclude_dir_relpaths = set()
    for item in exclude_dirs:
        p = Path(item)
        if p.is_absolute():
            exclude_dir_names.add(p.name)
        else:
            exclude_dir_names.add(p.name)
            exclude_dir_relpaths.add(str(p))

    # Normalize excludes for files
    exclude_file_names = set()
    exclude_file_relpaths = set()
    for item in exclude_files:
        p = Path(item)
        if p.is_absolute():
            exclude_file_names.add(p.name)
        else:
            exclude_file_names.add(p.name)
            exclude_file_relpaths.add(str(p))

    html_files: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current = Path(dirpath)

        # Prune subdirectories to exclude [web:41][web:51]
        pruned = []
        for d in dirnames:
            rel = (current / d).relative_to(root)
            if d in exclude_dir_names or str(rel) in exclude_dir_relpaths:
                pruned.append(d)
        dirnames[:] = [d for d in dirnames if d not in pruned]

        # Collect HTML files, filtering out excluded files
        for fname in filenames:
            if not fname.lower().endswith(".html"):
                continue
            full = current / fname
            rel = full.relative_to(root)
            if fname in exclude_file_names or str(rel) in exclude_file_relpaths:
                continue
            html_files.append(full)

    return html_files


def build_link_graph(html_files: List[Path]) -> Dict[Path, Set[Path]]:
    """
    Build a directed graph of local HTML links.

    Only considers:
      - relative links (no http://, https://, mailto:, etc.)
      - links that resolve to existing .html files
    Self-links are ignored.
    """
    canon_map: Dict[Path, Path] = {}
    for f in html_files:
        canon_map[f.resolve()] = f

    graph: Dict[Path, Set[Path]] = {f: set() for f in html_files}

    for src in html_files:
        src_resolved = src.resolve()
        text = src.read_text(encoding="utf-8", errors="ignore")
        parser = LinkExtractor()
        parser.feed(text)

        for href in parser.links:
            if not href or href.startswith("#"):
                continue
            if ":" in href.split("/", 1)[0]:
                continue
            if href.startswith("/"):
                continue

            target = (src.parent / href).resolve()

            for sep in ("?", "#"):
                if sep in target.name:
                    target = target.with_name(target.name.split(sep, 1)[0])

            # Ignore self-links
            if target == src_resolved:
                continue

            if target in canon_map:
                graph[src].add(canon_map[target])

    return graph


def build_backlinks(graph: Dict[Path, Set[Path]]) -> Dict[Path, Set[Path]]:
    backlinks: Dict[Path, Set[Path]] = {f: set() for f in graph.keys()}
    for src, targets in graph.items():
        for tgt in targets:
            backlinks[tgt].add(src)
    return backlinks


def write_link_report(
    root: Path,
    backlinks: Dict[Path, Set[Path]],
    report_path: Path | None = None,
) -> Path:
    if report_path is None:
        report_path = root / "html_link_report.txt"

    lines: List[str] = []
    lines.append(f"HTML link report for root: {root}\n")
    for target in sorted(backlinks.keys(), key=lambda p: str(p.relative_to(root))):
        rel_target = target.relative_to(root)
        lines.append(str(rel_target))
        sources = sorted(backlinks[target], key=lambda p: str(p.relative_to(root)))
        if not sources:
            lines.append("  - linked from: (none)")
        else:
            for src in sources:
                rel_src = src.relative_to(root)
                lines.append(f"  - linked from: {rel_src}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def check_html_backlinks(
    root_folder: str,
    exclude_dirs: Iterable[str] = (),
    exclude_files: Iterable[str] = (),
):
    root = Path(root_folder).resolve()
    if not root.is_dir():
        raise ValueError(f"{root_folder!r} is not a directory")

    html_files = find_html_files(
        root, exclude_dirs=exclude_dirs, exclude_files=exclude_files
    )
    if not html_files:
        print("No HTML files found.")
        return

    graph = build_link_graph(html_files)
    backlinks = build_backlinks(graph)

    unreferenced = [f for f in html_files if not backlinks[f]]

    if not unreferenced:
        print("OK: every HTML file is linked to by at least one other HTML file.")
    else:
        print(
            "The following HTML files are NOT linked to by any other local HTML file:"
        )
        for f in sorted(unreferenced):
            print(" -", f.relative_to(root))

    report_file = write_link_report(root, backlinks)
    print(f"Full link report written to: {report_file}")


def parse_args() -> argparse.Namespace:
    """
    Use argparse to define:
      positional: root folder
      optional: --exclude-dirs, --exclude-files (each accepts 0+ values)
    """
    parser = argparse.ArgumentParser(
        description="Verify local HTML backlinks and produce a report."
    )
    parser.add_argument(
        "root",
        help="Root folder to scan for HTML files.",
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs="*",
        default=[],
        help="Subdirectories (names or root-relative paths) to exclude.",
    )
    parser.add_argument(
        "--exclude-files",
        nargs="*",
        default=[],
        help="HTML files (names or root-relative paths) to exclude.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    check_html_backlinks(
        args.root,
        exclude_dirs=args.exclude_dirs,
        exclude_files=args.exclude_files,
    )
