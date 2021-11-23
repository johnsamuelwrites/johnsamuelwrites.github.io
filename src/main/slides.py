#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Numbering the slides

import argparse
from shutil import copy
from os import remove
import re


def enumerate_slides(filename):
    outputfile = open("/tmp/temp.html", "w")

    count = 1

    # Setting up regular expressions
    regex1 = re.compile(r'<section class="slide" id="slide[0-9]*">.*$',
                        re.IGNORECASE)
    regex2 = re.compile(r'<div class="navigation">[0-9]*',
                        re.IGNORECASE)
    regex3 = re.compile(r'<a class="prev" href="#slide[0-9]*">',
                        re.IGNORECASE)
    regex4 = re.compile(r'<a class="next" href="#slide[0-9]*">',
                        re.IGNORECASE)
    with open(filename, "r") as inputfile:
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
                '<section class="slide" id="slide%d">' % count, line)
            innersectionline2 = regex2.sub(
                '<div class="navigation">%d' % count, line)
            innersectionline3 = regex3.sub(
                '<a class="prev" href="#slide%d">' % (count-1), line)
            newsectionline = regex4.sub(
                '<a class="next" href="#slide%d">' % (count+1), line)

            if (line != newsectionline):
                line = newsectionline
                # incrementing section number
                count = count + 1
            elif (line != innersectionline1):
                line = innersectionline1
            elif (line != innersectionline2):
                line = innersectionline2
            elif (line != innersectionline3):
                line = innersectionline3
            else:
                # No change, but section number need to be incremented
                if ('<a class="next" href="#slide' in line):
                    count = count + 1

            outputfile.write(line+"\n")
    outputfile.close()
    inputfile.close()

    # Replacing the old file
    remove(filename)
    copy("/tmp/temp.html", filename)
    remove("/tmp/temp.html")


def modify_files(files):
    for filename in files:
        enumerate_slides(filename)


parser = argparse.ArgumentParser(description='Numbering the slides')
parser.add_argument('files', metavar='F', type=str, nargs='+',
                    help='HTML file')

args = parser.parse_args()
modify_files(args.files)
