#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Unified entry point for executable scripts in ``src/main``."""

from __future__ import annotations

import argparse
import runpy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from config import ALLOWED_UNREFERENCED_HTML_FILES, EXCLUDED_DIRECTORIES

@dataclass(frozen=True)
class CommandSpec:
    """Describe a script exposed by the unified CLI."""

    name: str
    script: str
    description: str
    aliases: tuple[str, ...] = ()


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("batch-translate", "batch_translate.py", "Manage translation workflows.", ("batch_translate",)),
    CommandSpec("blog", "blog.py", "Generate the blog index and feeds."),
    CommandSpec("build", "", "Run the default static-site build workflow."),
    CommandSpec(
        "build-all-search-indexes",
        "build-all-search-indexes.py",
        "Generate search indexes for all supported languages.",
        ("build_all_search_indexes",),
    ),
    CommandSpec("check", "", "Run the default static-site validation workflow."),
    CommandSpec("check-db", "check_db.py", "Inspect translation path mappings.", ("check_db",)),
    CommandSpec("ci-internal-links", "ci_internal_links.py", "Run CI internal-link checks.", ("ci_internal_links",)),
    CommandSpec(
        "convert-thumbnails",
        "convert_thumbnails.py",
        "Convert Wikimedia thumbnail URLs in HTML files.",
        ("convert_thumbnails",),
    ),
    CommandSpec(
        "generate-overview",
        "generate_overview.py",
        "Generate the translation overview report.",
        ("generate_overview",),
    ),
    CommandSpec("html-generator", "html_generator.py", "Generate translated HTML files.", ("html_generator",)),
    CommandSpec("links", "links.py", "Run link checks."),
    CommandSpec("list-files", "list_files.py", "List files with filtering options.", ("list_files",)),
    CommandSpec("metadata", "metadata.py", "Inspect metadata in HTML files."),
    CommandSpec("slides", "slides.py", "Renumber slide navigation."),
    CommandSpec("style", "style.py", "Replace embedded CSS in HTML files."),
    CommandSpec("template", "template.py", "Replace HTML template sections."),
    CommandSpec(
        "translate-manager",
        "translate_manager.py",
        "Manage translation memory and mappings.",
        ("translate_manager",),
    ),
    CommandSpec("verify-usage", "verify_usage.py", "Verify local HTML backlink usage.", ("verify_usage",)),
)

BASE_DIR = Path(__file__).resolve().parent
COMMAND_LOOKUP = {
    alias: command
    for command in COMMANDS
    for alias in (command.name, *command.aliases)
}


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        description="Unified command runner for src/main Python tools."
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run. Use 'list' to show the available tools.",
    )
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected command.",
    )
    return parser


def format_commands(commands: Iterable[CommandSpec]) -> str:
    """Build a readable command listing."""
    lines = ["Available commands:"]
    for command in commands:
        alias_suffix = f" (aliases: {', '.join(command.aliases)})" if command.aliases else ""
        lines.append(f"  {command.name:<24} {command.description}{alias_suffix}")
    return "\n".join(lines)


def run_script(script_name: str, argv: list[str]) -> int:
    """Execute a script in-process while preserving the requested argv."""
    script_path = BASE_DIR / script_name
    previous_argv = sys.argv[:]

    try:
        sys.argv = [str(script_path), *argv]
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit as exc:
            if exc.code is None:
                return 0
            if isinstance(exc.code, int):
                return exc.code
            print(exc.code)
            return 1
    finally:
        sys.argv = previous_argv

    return 0


def run_workflow(script_runs: Iterable[tuple[str, list[str]]]) -> int:
    """Run a sequence of script commands and stop on the first failure."""
    for script_name, script_argv in script_runs:
        exit_code = run_script(script_name, script_argv)
        if exit_code != 0:
            return exit_code
    return 0


def run_builtin_command(command_name: str, forwarded_args: list[str]) -> int | None:
    """Handle built-in orchestration commands."""
    if command_name == "check":
        parser = argparse.ArgumentParser(
            prog="python src/main/main.py check",
            description="Run offline-first validation: internal links and backlink usage.",
        )
        parser.add_argument(
            "--json-report-dir",
            help="Optional directory where JSON reports should be written.",
        )
        parsed = parser.parse_args(forwarded_args)
        exclude_args = [
            argument
            for exclude_dir in EXCLUDED_DIRECTORIES
            for argument in ("--exclude-dir", exclude_dir)
        ]
        links_args = ["--recursive", "--no-external", *exclude_args, "."]
        verify_args = [
            ".",
            "--exclude-dirs",
            *EXCLUDED_DIRECTORIES,
            "--exclude-files",
            *ALLOWED_UNREFERENCED_HTML_FILES,
            "--json-report",
        ]
        if parsed.json_report_dir:
            report_dir = Path(parsed.json_report_dir)
            report_dir.mkdir(parents=True, exist_ok=True)
            links_args.extend(["--json-report", str(report_dir / "links-report.json")])
            verify_args.extend(
                ["--json-report-path", str(report_dir / "verify-usage-report.json")]
            )
        return run_workflow(
            (
                ("links.py", links_args),
                ("verify_usage.py", verify_args),
            )
        )
    if command_name == "build":
        parser = argparse.ArgumentParser(
            prog="python src/main/main.py build",
            description="Run the default static-site build: blog, search indexes, and overview.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate outputs even when individual generators are current.",
        )
        parser.add_argument(
            "--languages",
            nargs="*",
            help="Optional subset of language codes for search index generation.",
        )
        parsed = parser.parse_args(forwarded_args)
        blog_args = ["--force"] if parsed.force else []
        search_args = []
        overview_args = ["--force"] if parsed.force else []
        if parsed.force:
            search_args.append("--force")
        if parsed.languages:
            search_args.extend(parsed.languages)
        return run_workflow(
            (
                ("blog.py", blog_args),
                ("build-all-search-indexes.py", search_args),
                ("generate_overview.py", overview_args),
            )
        )
    return None


def main(argv: list[str] | None = None) -> int:
    """Dispatch to a concrete tool in ``src/main``."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command in {"help", "list"}:
        print(format_commands(COMMANDS))
        return 0 if not args.command or args.command == "list" else 0

    command = COMMAND_LOOKUP.get(args.command)
    if command is None:
        parser.error(f"unknown command: {args.command}")

    forwarded_args = list(args.command_args)
    if forwarded_args and forwarded_args[0] == "--":
        forwarded_args = forwarded_args[1:]

    builtin_result = run_builtin_command(args.command, forwarded_args)
    if builtin_result is not None:
        return builtin_result

    return run_script(command.script, forwarded_args)


if __name__ == "__main__":
    raise SystemExit(main())
