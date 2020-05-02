import extruct
import requests
import pprint
import argparse
from w3lib.html import get_base_url

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
parser.add_argument('link', metavar='link', type=str, nargs='+',
                    help='link or paths of html file')

args = parser.parse_args()
if (args.link is None):
 parser.print_usage()
 exit(1)
extract_metadata(args.link)
