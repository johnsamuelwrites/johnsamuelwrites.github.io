# Check the presence of broken links in one or more HTML files 
# Author: John Samuel

'''
  This will take one or more input HTML files.
  If there is a broken link (http, https or file protocol), it will
  show them on the screen
'''
import argparse
from bs4 import BeautifulSoup
import os
import requests

def check_broken_links_file(filepath):
  with open(filepath,"r") as inputfile:
    content = inputfile.read()
    parsed_html = BeautifulSoup(content, features='html.parser')
    for link in parsed_html.find_all('a'):
      source = link.get('href')
      if ( source.startswith('http') or
           source.startswith('https')):
        headers={'User-Agent': 'Mozilla/5.0'}
        request = requests.get(source, headers=headers)
        # Try to access the web page and check the status code
        if not request.status_code == 200:
          print(str(request.status_code) + ":  " + source)
      elif not source.startswith('#'):
         dirpath = os.path.dirname(os.path.abspath(filepath))
         if not os.path.isfile(dirpath + "/" + source):
           print(source)


def check_broken_links_files(filepaths):
  for filepath in filepaths:
    print("====== "+filepath + " ======")
    check_broken_links_file(filepath)

parser = argparse.ArgumentParser(description='check if links are broken')
parser.add_argument('files', metavar='F', type=str, nargs='+',
                    help='HTML file(s)')

args = parser.parse_args()

# style file and HTML file
if(len(args.files) < 1):
  parser.print_usage()
  exit(1)

check_broken_links_files(args.files)

