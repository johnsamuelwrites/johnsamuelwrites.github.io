# Add, update and extract metadata (RDFa, JSON-LD, microdata) of a web page
# Author: John Samuel

import extruct
import requests
import pprint
import argparse
from w3lib.html import get_base_url
from pygit2 import Repository, GIT_BLAME_TRACK_COPIES_SAME_FILE, GIT_SORT_TOPOLOGICAL, GIT_SORT_REVERSE
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from shutil import copy
from os import remove

jsonld_template = """
{
    "@context" : "http://schema.org",
    "@type" : "BlogPosting",
    "mainEntityOfPage": {
         "@type": "WebPage",
         "@id": "https://johnsamuel.info"
    },
    "articleSection" : "blog",
    "name" : "",
    "headline" : "",
    "description" : "",
    "inLanguage" : "en",
    "author" : "John Samuel",
    "datePublished": "",
    "dateModified" : "",
    "dateCreated" : "",
    "url" : "",
    "keywords" : ["Blog" ]
}
"""

def get_modification_publication(filepath):
  repo = Repository('.git')
  latest = None
  first = None
  blame = repo.blame(filepath, flags=GIT_BLAME_TRACK_COPIES_SAME_FILE)
  for b in blame:
    commit = repo.get(b.final_commit_id)
    if not latest:
      latest = commit.commit_time
    elif latest < commit.commit_time:
      latest = commit.commit_time
    if not first:
      first = commit.commit_time
    elif first > commit.commit_time:
      first = commit.commit_time
  return first, latest

def replace_name(title):
  title = title.replace("John Samuel", "")
  title = title.replace("ജോൺ ശമൂവേൽ", "")
  title = title.replace("ਜੌਨ ਸੈਮੂਅਲ", "")
  title = title.replace("जॉन शमुऐल", "")
  return title

def add_update_metadata(links):

  #Setting up regular expression for json-ld script
  pattern = r'<script type="application\/ld\+json">(\n|.)*script>'

  headpattern = r'<head.*>(\n|.)*<\/head>'

  for link in links:
    # only with files
    if (not link.startswith("http")):
      with open(link, "r") as f:
        content = f.read()
        jsonld = json.loads(jsonld_template)
        # get creation, publication and modification date
        first, latest = get_modification_publication(link)
        jsonld["dateCreated"] = str(datetime.fromtimestamp(first))
        jsonld["datePublished"] = str(datetime.fromtimestamp(first))
        jsonld["dateModified"] = str(datetime.fromtimestamp(latest))

        # get title
        parsed_html = BeautifulSoup(content, features='html.parser')
        for titletag in parsed_html.find_all('title'):
          title = replace_name(titletag.text)
          title = title.replace(":", "")
          title = title.strip()
        jsonld["name"] = title
        jsonld["description"] =  "Article by John Samuel"
        # Care must be taken to ensure the link exists
        jsonld["url"] = "https://johnsamuel.info/" + link
        jsonld["headline"] = title
        scriptjsonld = '<script type="application/ld+json">\n      '+ json.dumps(jsonld) + "\n    </script>"
        if ("application/ld+json" not in content):
          content = content.replace("</head>", scriptjsonld + "\n  </head>")
        else:
          content = re.sub(pattern, scriptjsonld, content)
        outputfile = open("/tmp/temp.html", "w") 

        outputfile.write(content)

        f.close()
        outputfile.close()

        #Replacing the old file
        remove(link)
        copy("/tmp/temp.html", link)
        remove("/tmp/temp.html")



def extract_metadata(links):
  for link in links:
    print("=======" + link + "========")
    pp = pprint.PrettyPrinter(indent=2)
    data = None
    if (link.startswith("http")):
      r = requests.get(link)
      base_url = get_base_url(r.text, r.url)
      data = extruct.extract(r.text, base_url=base_url)
    else:
      with open(link, "r") as f:
        data = extruct.extract(f.read())
    pp.pprint(data)

parser = argparse.ArgumentParser(description='set or extract metadata form a URL or a file')
subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')


# create the parser for the "extract" command
parser_extract = subparsers.add_parser('extract', help='extract metadata')
parser_extract.add_argument('link', metavar='link', type=str, nargs='+',
                    help='link or paths of html file')
parser_extract.set_defaults(func=extract_metadata)
 
# create the parser for the "add" command
parser_add = subparsers.add_parser('add', help='add metadata')
parser_add.add_argument('link', metavar='link', type=str, nargs='+',
                    help='link or paths of html file')
parser_add.set_defaults(func=add_update_metadata)

args = parser.parse_args()
# args.subparser_name contains the name of the subcommand
# since we have link as a parameter for both the command
args.func(args.link)