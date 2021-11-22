#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Change the section of one or more HTML files

'''
  This will take one or more input HTML files and a single CSS file.
  Content between <template> and </template> will be replaced by the contents 
  of the CSS file
'''

import argparse
from shutil import copy
from os import remove
import re

def modify_content(filename):
  outputfile = open("/tmp/temp.html", "w") 

  #Setting up regular expression for template
  pattern = r'(<div class="title">(\n|.)*?</div>(\n|.)*?<div class="subtitle">(\n|.)*?</div>)'
 
  content = ""
  template = r'<div id="sidebar">\n      \1\n      </div>'
  with open(filename,"r") as inputfile:
    content = inputfile.read()
  content = re.sub(pattern, template, content)
  outputfile.write(content)

  outputfile.close()
  inputfile.close()

  #Replacing the old file
  remove(filename)
  copy("/tmp/temp.html", filename)
  remove("/tmp/temp.html")

def remove_content(filename, patterns):
  outputfile = open("/tmp/temp.html", "w") 

  content = ""
  template = ""
  with open(filename,"r") as inputfile:
    content = inputfile.read()
  for pattern in patterns:
    content = re.sub(pattern, template, content)

  outputfile.write(content)

  outputfile.close()
  inputfile.close()

  #Replacing the old file
  remove(filename)
  copy("/tmp/temp.html", filename)
  remove("/tmp/temp.html")

def add_content(filename, templatefilepath):
  outputfile = open("/tmp/temp.html", "w") 

  #Setting up regular expression for template
  pattern = r'<div class="home">(\n|.)*?</div>'
 
  content = ""
  template = ""
  with open(filename,"r") as inputfile:
    content = inputfile.read()
  with open(templatefilepath,"r") as templatefile:
    template = templatefile.read()
  template = '<div class="home">\n'+ template + "\n      </div>"
  content = re.sub(pattern, template, content)
  outputfile.write(content)

  templatefile.close()
  outputfile.close()
  inputfile.close()

  #Replacing the old file
  remove(filename)
  copy("/tmp/temp.html", filename)
  remove("/tmp/temp.html")

def modify_files(files):
  inputfiles = files[:len(files)-1]
  templatefile = files[len(files)-1]
  for filename in inputfiles:
    print(filename, templatefile)
    patterns = [r'<div class="licence">(\n|.)*?</div>',
               r'<div class="separator" id="top">(\n|.)*?</div>',
               r'<div class="separator" id="bottom">(\n|.)*?</div>']
    add_content(filename, templatefile)
    remove_content(filename, patterns)
    modify_content(filename)
  

parser = argparse.ArgumentParser(description='change section of HTML file')
parser.add_argument('files', metavar='F', type=str, nargs='+',
                    help='HTML header file')

args = parser.parse_args()

# template file and HTML file
if(len(args.files) < 2):
  parser.print_usage()
  exit(1)
modify_files(args.files)

