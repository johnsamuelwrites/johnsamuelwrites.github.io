# Generate an upto date list of articles in reverse chronological order 
# Author: John Samuel

'''
  This program does not take any input from the command line
  However a list of directories and files can be specified in the variables
  'directories' and 'files'.
  A list of files to be excluded can also be specified
'''
import sys
from bs4 import BeautifulSoup
import os
from pygit2 import Repository, GIT_BLAME_TRACK_COPIES_SAME_FILE, GIT_SORT_TOPOLOGICAL, GIT_SORT_REVERSE
from datetime import datetime
import bisect

directories = {}
directories["en"] = [
   "en/blog",
   "en/photography",  
   "en/research",
   "en/teaching",
   "en/writings",
   "en/linguistics",
   "en/programming",
   "en/slides",
   "en/technology",
   "en/travel"
  ]

directories["fr"] = [
   "fr/blog",
   "fr/enseignement",
   "fr/linguistique",
   "fr/programmation",
   "fr/technologie",
   "fr/voyages",
   "fr/ecrits",
   "fr/photographie",
   "fr/recherche"
]

exclude_files = {
   "en/blog/index.html",
   "en/photography/index.html",  
   "en/research/index.html",
   "en/teaching/index.html",
   "en/writings/index.html",
   "en/linguistics/index.html",
   "en/programming/index.html",
   "en/slides/index.html",
   "en/technology/index.html",
   "en/travel/index.html",
   "fr/blog/index.html",
   "fr/enseignement/index.html",
   "fr/linguistique/index.html",
   "fr/programmation/index.html",
   "fr/technologie/index.html",
   "fr/voyages/index.html",
   "fr/ecrits/index.html",
   "fr/photographie/index.html",
   "fr/recherche/index.html",
   "en/blog/template.html",
   "en/photography/template.html",  
   "en/research/template.html",
   "en/teaching/template.html",
   "en/writings/template.html",
   "en/linguistics/template.html",
   "en/programming/template.html",
   "en/slides/template.html",
   "en/technology/template.html",
   "en/travel/template.html",
   "fr/blog/template.html",
   "fr/enseignement/template.html",
   "fr/linguistique/template.html",
   "fr/programmation/template.html",
   "fr/technologie/template.html",
   "fr/voyages/template.html",
   "fr/ecrits/template.html",
   "fr/photographie/template.html",
   "fr/recherche/template.html",
}

def get_latest_modification(filepath):
  repo = Repository('.git')
  latest = None
  blame = repo.blame(filepath, flags=GIT_BLAME_TRACK_COPIES_SAME_FILE)
  for b in blame:
    commit = repo.get(b.final_commit_id)
    if not latest:
      latest = commit
    elif latest.commit_time < commit.commit_time:
      latest = commit
  return latest

def check_for_modified_articles():
  articles = {}
  modification_time_list = []
  for language in directories:
    for directory in directories[language]:
      try:
        for filename in os.listdir(directory):
          filepath = directory+"/"+filename
          if(os.path.isfile(filepath) and filepath not in exclude_files):
            with open (filepath, "r") as f:
              if("NOTE: Article in Progress" not in f.read()):
                latest = get_latest_modification(filepath)  
                bisect.insort(modification_time_list, latest.commit_time) 
                if latest.commit_time not in articles:
                  articles[latest.commit_time] = [filepath]
                else:
                  articles[latest.commit_time].append(filepath)

      except Exception as e:
        print("Error: " + str(e))
  for time in modification_time_list[::-1]: 
    for article in articles[time]:
      print(article, datetime.fromtimestamp(time).strftime('%d %B %Y'))

if(len(sys.argv) > 1):
 print("The program takes no input")
 exit(1)

check_for_modified_articles()
