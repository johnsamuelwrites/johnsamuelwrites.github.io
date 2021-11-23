#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Change the style of one or more HTML files

'''
  This will take one or more input HTML files and a single CSS file.
  Content between <style> and </style> will be replaced by the contents 
  of the CSS file
'''

import argparse
from shutil import copy
from os import remove
import re


def change_style(filename, stylefilepath):
    outputfile = open("/tmp/temp.html", "w")

    # Setting up regular expression for style
    pattern = r'<style.*>(\n|.)*style>'

    content = ""
    style = ""
    with open(filename, "r") as inputfile:
        content = inputfile.read()
    with open(stylefilepath, "r") as stylefile:
        style = stylefile.read()
    style = '<style type="text/css">\n' + style + "\n    </style>"
    content = re.sub(pattern, style, content)
    outputfile.write(content)

    stylefile.close()
    outputfile.close()
    inputfile.close()

    # Replacing the old file
    remove(filename)
    copy("/tmp/temp.html", filename)
    remove("/tmp/temp.html")


def modify_files(files):
    inputfiles = files[:len(files)-1]
    stylefile = files[len(files)-1]
    for filename in inputfiles:
        print(filename, stylefile)
        change_style(filename, stylefile)


parser = argparse.ArgumentParser(description='change style of HTML file')
parser.add_argument('files', metavar='F', type=str, nargs='+',
                    help='HTML CSS style filse')

args = parser.parse_args()

# style file and HTML file
if(len(args.files) < 2):
    parser.print_usage()
    exit(1)
modify_files(args.files)
