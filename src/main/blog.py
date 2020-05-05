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
from git import get_first_latest_modification
from datetime import datetime
import bisect
from shutil import copy
from os import remove
from feedgen.feed import FeedGenerator
from pytz import timezone

directories = {}
directories["en"] = [
   "en",
   "en/blog",
   "en/photography",  
   "en/research",
   "en/teaching",
   "en/writings",
   "en/linguistics",
   "en/programming",
   "en/slides",
   "en/technology",
   "en/travel",
   "en/slides/2017/Akademy/html",
   "en/slides/2017/CapitoleduLibre/html",
   "en/slides/2017/XLDB/html",
   "en/slides/2018/CLEF",
   "en/slides/2018/SWIB",
   "en/slides/2018/UNILOG",
   "en/slides/2018/WikimediaHackathon",
   "en/slides/2018/WikiWorkshop",
   "en/slides/2019/Catai",
   "en/slides/2019/WikidataCon",
   "en/slides/2020/EUvsVirus"
  ]

directories["fr"] = [
   "fr",
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

directories["ml"] = [
   "ml"
]

directories["hi"] = [
   "hi"
]

directories["pa"] = [
   "pa"
]

exclude_files = {
   "en/template.html",
   "fr/template.html",
   "en/slides/2017/Akademy/html/kde-wikidata.html",
   "fr/blog/index.html",
   "fr/linguistique/index.html",
   "fr/programmation/index.html",
   "fr/technologie/index.html",
   "fr/voyages/index.html",
   "fr/ecrits/index.html",
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


def replace_name(title):
  title = title.replace("John Samuel", "")
  title = title.replace("ജോൺ ശമൂവേൽ", "")
  title = title.replace("ਜੌਨ ਸੈਮੂਅਲ", "")
  title = title.replace("जॉन शमुऐल", "")
  return title

def check_for_modified_articles():
  articles = {}
  articleset = set()
  modification_time_list = []
  for language in directories:
    for directory in directories[language]:
      try:
        filepath = None
        for filename in os.listdir(directory):
          if ".html" not in filename:
            continue
          filepath = directory+"/"+filename
          if(os.path.isfile(filepath) and filepath not in exclude_files):
            with open (filepath, "r") as f:
              if("NOTE: Article in Progress" not in f.read()):
                first, latest = get_first_latest_modification(filepath)  
                bisect.insort(modification_time_list, latest) 
                if latest not in articles:
                  articles[latest] = {filepath}
                else:
                  articles[latest].add(filepath)

      except Exception as e:
        print("Error: in file: " + filepath + ": " + str(e))

  fg = FeedGenerator()
  fg.id("https://johnsamuel.info")
  fg.title("John Samuel")
  fg.description('Personal Blog of John Samuel')
  fg.author( {'name':'John Samuel'} )
  fg.language('en')
  fg.link(href="https://johnsamuel.info")
  count = {}
  articlelist = {}
  for lang in ["en", "fr", "hi", "pa", "ml"]:
    count[lang] = 1
    articlelist[lang] = "<ul vocab='http://schema.org/' typeof='BreadcrumbList'>"
  for time in modification_time_list[::-1]: 
    for article in articles[time]:
      title = None
      if (article in articleset):
        continue
      articleset.add(article)
      with open(article,"r") as inputfile:
        content = inputfile.read()
        parsed_html = BeautifulSoup(content, features='html.parser')
        for link in parsed_html.find_all('title'):
          title = replace_name(link.text)
          title = title.replace(":", "")
          title = title.strip()
          #display modification date of article along with the title
          line = "\n<li property='itemListElement' typeof='ListItem'><a property='item' typeof='WebPage' href='../"+ article + "'>" + "<span property='name'>" + title + "</span></a>" + " <span class='date' property='datePublished' content='" + datetime.fromtimestamp(time).strftime('%Y-%m-%d') + "'>" + datetime.fromtimestamp(time).strftime('%d %B %Y') + "</span>" 
          for lang in ["en", "fr", "hi", "pa", "ml"]:
            if article.startswith(lang):
              articlelist[lang] = articlelist[lang] + line + '<meta property="position" content="' + str(count[lang]) + '"></li>'
              count[lang] = count[lang] + 1
              break
          fe = fg.add_entry(order='append')
          fe.id("https://johnsamuel.info/" + article.strip())
          fe.title(title.strip())
          fe.pubDate(datetime.fromtimestamp(time, tz=timezone('Europe/Amsterdam')))
          fe.description(title)
          fe.link(href="https://johnsamuel.info/"+article.strip())

  for lang in ["en", "fr", "hi", "pa", "ml"]:
    articlelist[lang] = articlelist[lang] + "\n</ul>"
  with open("templates/blog.html", "r") as blogtemplate:
    content = blogtemplate.read()
    content = content.replace("EnglishArticleList", articlelist["en"])
    content = content.replace("FrenchArticleList", articlelist["fr"])
    content = content.replace("HindiArticleList", articlelist["hi"])
    content = content.replace("MalayalamArticleList", articlelist["ml"])
    content = content.replace("PunjabiArticleList", articlelist["pa"])
    with open("blog/index.html", "w") as blog:
      blog.write(content)
    blog.close()
  blogtemplate.close()

  # Writing the feed
  atomfeed = fg.atom_str(pretty=True)
  rssfeed  = fg.rss_str(pretty=True)
  fg.atom_file('atom.xml')
  fg.rss_file('rss.xml')


if(len(sys.argv) > 1):
 print("The program takes no input")
 exit(1)

check_for_modified_articles()
