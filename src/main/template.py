#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Change the section of one or more HTML files

"""
This will take one or more input HTML files and a single CSS file.
Content between <template> and </template> will be replaced by the contents
of the CSS file
"""

import argparse
import re

from file_rewrite import rewrite_text_file


def modify_content(filename):
    # Setting up regular expression for template
    pattern = r'(<div class="title">(\n|.)*?</div>(\n|.)*?<div class="subtitle">(\n|.)*?</div>)'
    template = r'<div id="sidebar">\n      \1\n      </div>'
    rewrite_text_file(filename, lambda content: re.sub(pattern, template, content))


def remove_content(filename, patterns):
    def transform(content):
        for pattern in patterns:
            content = re.sub(pattern, "", content)
        return content

    rewrite_text_file(filename, transform)


def add_content(filename, templatefilepath):
    # Setting up regular expression for template
    pattern = r'<div class="home">(\n|.)*?</div>'

    with open(templatefilepath, "r", encoding="utf-8") as templatefile:
        template = templatefile.read()
    replacement = '<div class="home">\n' + template + "\n      </div>"
    rewrite_text_file(filename, lambda content: re.sub(pattern, replacement, content))


def modify_files(files):
    inputfiles = files[: len(files) - 1]
    templatefile = files[len(files) - 1]
    for filename in inputfiles:
        print(filename, templatefile)
        patterns = [
            r'<div class="licence">(\n|.)*?</div>',
            r'<div class="separator" id="top">(\n|.)*?</div>',
            r'<div class="separator" id="bottom">(\n|.)*?</div>',
        ]
        add_content(filename, templatefile)
        remove_content(filename, patterns)
        modify_content(filename)

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="change section of HTML file")
    parser.add_argument(
        "files", metavar="F", type=str, nargs="+", help="HTML header file"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if len(args.files) < 2:
        print("Usage: template.py <html-file> [<html-file> ...] <template-file>")
        return 1
    modify_files(args.files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
