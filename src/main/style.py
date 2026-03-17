#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Change the style of one or more HTML files

"""
This will take one or more input HTML files and a single CSS file.
Content between <style> and </style> will be replaced by the contents
of the CSS file
"""

import argparse
import re

from file_rewrite import rewrite_text_file


def change_style(filename, stylefilepath):
    # Setting up regular expression for style
    pattern = r"<style.*>(\n|.)*style>"

    with open(stylefilepath, "r", encoding="utf-8") as stylefile:
        style = stylefile.read()

    replacement = '<style type="text/css">\n' + style + "\n    </style>"
    rewrite_text_file(filename, lambda content: re.sub(pattern, replacement, content))


def modify_files(files):
    inputfiles = files[: len(files) - 1]
    stylefile = files[len(files) - 1]
    for filename in inputfiles:
        print(filename, stylefile)
        change_style(filename, stylefile)

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="change style of HTML file")
    parser.add_argument(
        "files", metavar="F", type=str, nargs="+", help="HTML CSS style files"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if len(args.files) < 2:
        print("Usage: style.py <html-file> [<html-file> ...] <css-file>")
        return 1
    modify_files(args.files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
