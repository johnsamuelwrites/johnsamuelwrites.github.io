#!/usr/bin/env python3
"""Fallback converter: pipe-separated QuickStatements -> TAB-separated.

The generators in this package emit pipe-separated QuickStatements, which is the
preferred format. QuickStatements accepts ``TAB`` *or* ``|`` as the field
separator, but it has no ``\\|`` escape, so a value that itself contains a
literal ``|`` (for example an HTML ``<title>`` such as ``"Model | Project 3D"``)
cannot be represented while ``|`` is also the separator. When a batch contains
such values, run it through this converter to obtain an equivalent TAB-separated
file that imports correctly.

This is a fallback only; the primary output stays pipe-separated. The converter
rewrites separator pipes (those outside quoted strings) as TABs, restores
``\\|`` to a literal ``|``, and converts backslash-escaped quotes to the
QuickStatements ``""`` form.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def pipe_to_tab_line(line: str) -> str:
    """Convert one pipe-separated QuickStatements line to TAB-separated.

    Pipes outside quoted strings are separators and become TABs. Inside a quoted
    string, ``\\|`` and ``\\\\`` are unescaped to their literal character and
    ``\\"`` becomes ``""`` (QuickStatements escapes quotes by doubling them).
    """
    out: list[str] = []
    in_quote = False
    index = 0
    length = len(line)
    while index < length:
        character = line[index]
        if not in_quote:
            if character == "|":
                out.append("\t")
            elif character == '"':
                in_quote = True
                out.append('"')
            else:
                out.append(character)
            index += 1
        elif character == "\\" and index + 1 < length:
            following = line[index + 1]
            out.append('""' if following == '"' else following)
            index += 2
        elif character == '"':
            in_quote = False
            out.append('"')
            index += 1
        else:
            out.append(character)
            index += 1
    return "".join(out)


def pipe_to_tab(text: str) -> str:
    """Convert pipe-separated QuickStatements text to TAB-separated text."""
    return "\n".join(pipe_to_tab_line(line) for line in text.splitlines())


def convert_file(source: Path, destination: Path) -> None:
    converted = pipe_to_tab(source.read_text(encoding="utf-8"))
    destination.write_text(converted + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="pipe-separated .quickstatements file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="destination file (default: <source stem>.tab.quickstatements)",
    )
    args = parser.parse_args()
    destination = args.output or args.source.with_suffix(".tab.quickstatements")
    try:
        convert_file(args.source, destination)
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
