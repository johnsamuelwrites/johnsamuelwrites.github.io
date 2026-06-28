#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

from links import LinkChecker, collect_html_files, print_results

IGNORED_DIRS = ("templates", "analysis")

# Directories skipped during a full-site scan. In addition to the directories
# ignored for changed-file checks, this excludes the tooling/source tree (which
# holds intentionally broken link fixtures used by the unit tests) and common
# vendored/VCS directories.
FULL_SCAN_IGNORED_DIRS = IGNORED_DIRS + ("src", "node_modules", ".git", ".github")


def is_ignored_html_file(path: Path, ignored_dirs: Iterable[str] = IGNORED_DIRS) -> bool:
    """Return True when the changed file is under an ignored directory."""
    ignored = set(ignored_dirs)
    return any(part in ignored for part in path.parts)


def resolve_all_html_files() -> List[str]:
    """Return every checkable HTML file in the repository (full-site scan)."""
    repo_root = Path.cwd().resolve()
    html_files = collect_html_files(
        [str(repo_root)],
        recursive=True,
        exclude_dirs=FULL_SCAN_IGNORED_DIRS,
    )
    return sorted(set(html_files))


def resolve_changed_html_files(diff_range: str) -> List[str]:
    """Return changed HTML files from a git diff range."""
    repo_root = Path.cwd().resolve()
    repo_root_for_git = repo_root.as_posix()
    zero_sha = "0" * 40
    if diff_range.startswith(f"{zero_sha}..."):
        diff_range = "HEAD^...HEAD"

    try:
        completed = subprocess.run(
            [
                "git",
                f"-c",
                f"safe.directory={repo_root_for_git}",
                "diff",
                "--name-only",
                diff_range,
                "--",
                "*.html",
                "*.htm",
                "*.xhtml",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        print(f"Unable to resolve changed HTML files for diff range {diff_range!r}.")
        if error.stderr:
            print(error.stderr.strip())
        return []
    html_files = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        candidate = (repo_root / line.strip()).resolve()
        if candidate.is_file() and not is_ignored_html_file(candidate.relative_to(repo_root)):
            html_files.append(str(candidate))
    return sorted(set(html_files))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run internal broken-link checks for HTML files in CI."
    )
    parser.add_argument(
        "--diff-range",
        default=os.environ.get("GITHUB_DIFF_RANGE"),
        help="Git diff range to inspect, for example BASE_SHA...HEAD_SHA.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=os.environ.get("LINK_CHECK_ALL", "").lower() in ("1", "true", "yes"),
        help=(
            "Scan every HTML file in the repository instead of only the files "
            "changed in the diff range. Use this to catch links that break when "
            "new files or folders are added."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Scan every HTML file under this path (for example Q315).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.root:
        root = args.root.resolve()
        html_files = collect_html_files(
            [str(root)],
            recursive=True,
            exclude_dirs=FULL_SCAN_IGNORED_DIRS,
        )
        html_files = sorted(set(html_files))
        if not html_files:
            print(f"No HTML files found under {args.root}.")
            return 0
        print(
            f"Scanning {len(html_files)} HTML files under {args.root} "
            "for internal broken links."
        )
    elif args.all:
        html_files = resolve_all_html_files()
        if not html_files:
            print("No HTML files found to check.")
            return 0
        print(f"Scanning all {len(html_files)} HTML files for internal broken links.")
    else:
        if not args.diff_range:
            print("No diff range supplied; skipping internal broken-link CI check.")
            return 0

        html_files = resolve_changed_html_files(args.diff_range)
        if not html_files:
            print("No changed HTML files found in the selected diff range.")
            return 0

    checker = LinkChecker(
        check_external=False,
        check_internal=True,
        check_favicon=False,
        check_styles=False,
        check_scripts=False,
    )
    results = checker.check_files(html_files)
    print_results(
        results,
        show_external=False,
        show_internal=True,
        show_favicon=False,
        show_styles=False,
        show_scripts=False,
    )
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
