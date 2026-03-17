#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Numbering the slides

import argparse
import re

from file_rewrite import rewrite_text_file


def enumerate_slides(filename):
    count = 1

    # Setting up regular expressions
    regex1 = re.compile(r'<section class="slide" id="slide[0-9]*">.*$', re.IGNORECASE)
    regex2 = re.compile(r'<div class="navigation">[0-9]*', re.IGNORECASE)
    regex3 = re.compile(r'<a class="prev" href="#slide[0-9]*">', re.IGNORECASE)
    regex4 = re.compile(r'<a class="next" href="#slide[0-9]*">', re.IGNORECASE)
    updated_lines = []

    with open(filename, "r", encoding="utf-8") as inputfile:
        for line in inputfile:
            # stripping the new line character (to later add it)
            line = line.rstrip()

            # Temporary copying the lines
            newsectionline = line
            innersectionline1 = line
            innersectionline2 = line
            innersectionline3 = line

            # Setting up regular expressions
            innersectionline1 = regex1.sub(
                '<section class="slide" id="slide%d">' % count, line
            )
            innersectionline2 = regex2.sub('<div class="navigation">%d' % count, line)
            innersectionline3 = regex3.sub(
                '<a class="prev" href="#slide%d">' % (count - 1), line
            )
            newsectionline = regex4.sub(
                '<a class="next" href="#slide%d">' % (count + 1), line
            )

            if line != newsectionline:
                line = newsectionline
                # incrementing section number
                count = count + 1
            elif line != innersectionline1:
                line = innersectionline1
            elif line != innersectionline2:
                line = innersectionline2
            elif line != innersectionline3:
                line = innersectionline3
            else:
                # No change, but section number need to be incremented
                if '<a class="next" href="#slide' in line:
                    count = count + 1

            updated_lines.append(line)

    rewrite_text_file(filename, lambda _content: "\n".join(updated_lines) + "\n")


def modify_files(files):
    for filename in files:
        enumerate_slides(filename)

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Numbering the slides")
    parser.add_argument("files", metavar="F", type=str, nargs="+", help="HTML file")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    modify_files(args.files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
