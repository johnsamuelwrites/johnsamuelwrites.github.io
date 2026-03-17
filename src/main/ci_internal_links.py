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
from typing import List

from links import LinkChecker, print_results


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
        if candidate.is_file():
            html_files.append(str(candidate))
    return sorted(set(html_files))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run internal broken-link checks for changed HTML files in CI."
    )
    parser.add_argument(
        "--diff-range",
        default=os.environ.get("GITHUB_DIFF_RANGE"),
        help="Git diff range to inspect, for example BASE_SHA...HEAD_SHA.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
