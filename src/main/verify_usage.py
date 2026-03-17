#
# SPDX-FileCopyrightText: 2025 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import argparse
import json
import sys
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, Set, List, Iterable

from config import EXCLUDED_DIRECTORIES
from links import collect_html_files


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


def write_json_report(
    root: Path,
    backlinks: Dict[Path, Set[Path]],
    report_path: Path | None = None,
) -> Path:
    if report_path is None:
        report_path = root / "html_link_report.json"

    payload = {
        "root": str(root),
        "pages": [
            {
                "path": str(target.relative_to(root)),
                "linked_from": [
                    str(source.relative_to(root))
                    for source in sorted(backlinks[target], key=lambda p: str(p.relative_to(root)))
                ],
            }
            for target in sorted(backlinks.keys(), key=lambda p: str(p.relative_to(root)))
        ],
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path


def check_html_backlinks(
    root_folder: str,
    exclude_dirs: Iterable[str] = (),
    exclude_files: Iterable[str] = (),
    json_report: bool = False,
    json_report_path: str | None = None,
) -> int:
    root = Path(root_folder).resolve()
    if not root.is_dir():
        raise ValueError(f"{root_folder!r} is not a directory")

    html_files = [
        Path(path)
        for path in collect_html_files(
            [str(root)], recursive=True, exclude_dirs=exclude_dirs
        )
    ]
    if exclude_files:
        excluded_file_paths = {str((root / path).resolve()) for path in exclude_files}
        excluded_names = {Path(path).name for path in exclude_files}
        html_files = [
            path
            for path in html_files
            if str(path.resolve()) not in excluded_file_paths
            and path.name not in excluded_names
        ]
    if not html_files:
        print("No HTML files found.")
        return 0

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
    if json_report:
        json_report_file = write_json_report(
            root,
            backlinks,
            Path(json_report_path) if json_report_path else None,
        )
        print(f"JSON link report written to: {json_report_file}")
    return 1 if unreferenced else 0


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
        default=list(EXCLUDED_DIRECTORIES),
        help="Subdirectories (names or root-relative paths) to exclude.",
    )
    parser.add_argument(
        "--exclude-files",
        nargs="*",
        default=[],
        help="HTML files (names or root-relative paths) to exclude.",
    )
    parser.add_argument(
        "--json-report",
        action="store_true",
        help="Also write a machine-readable JSON report.",
    )
    parser.add_argument(
        "--json-report-path",
        help="Optional explicit path for the JSON report.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(
        check_html_backlinks(
            args.root,
            exclude_dirs=args.exclude_dirs,
            exclude_files=args.exclude_files,
            json_report=args.json_report,
            json_report_path=args.json_report_path,
        )
    )
