#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


# Generate an upto date list of articles in reverse chronological order

"""
  This program does not take any input from the command line
  However a list of directories and files can be specified in the variables
  'directories' and 'files'.
  A list of files to be excluded can also be specified
"""
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
from analyse import WebsiteAnalysis
import pandas
import numpy as np


def replace_name(title):
    title = title.replace(": John Samuel", "")
    title = title.replace(": ജോൺ ശമൂവേൽ", "")
    title = title.replace(": ਜੌਨ ਸੈਮੂਅਲ", "")
    title = title.replace(": जॉन शमुऐल", "")
    return title


def check_for_modified_articles():
    article_metadata = []
    articleset = set()
    directories = WebsiteAnalysis.get_directories()
    for language in directories:
        for directory in directories[language]:
            try:
                filepath = None
                for filename in os.listdir(directory):
                    if ".html" not in filename:
                        continue
                    filepath = directory + "/" + filename
                    if (
                        os.path.isfile(filepath)
                        and filepath not in WebsiteAnalysis.get_excluded_files()
                    ):
                        with open(filepath, "r") as f:
                            if "NOTE: Article in Progress" not in f.read():
                                first, latest = get_first_latest_modification(filepath)
                                article_metadata.append([filepath, first, latest])

            except Exception as e:
                print("Error: in file: " + filepath + ": " + str(e))

    df = pandas.DataFrame(article_metadata, columns=["filepath", "first", "latest"])
    df = df.sort_values(["latest", "first"], ascending=[False, False])

    fg = FeedGenerator()
    fg.id("https://johnsamuel.info")
    fg.title("John Samuel")
    fg.description("Personal Blog of John Samuel")
    fg.author({"name": "John Samuel"})
    fg.language("en")
    fg.link(href="https://johnsamuel.info")
    count = {}
    articlelist = {}
    for lang in ["en", "fr", "hi", "pa", "ml"]:
        count[lang] = 1
        articlelist[lang] = "<ul vocab='http://schema.org/' typeof='ItemList'>"
    for index, row in df.iterrows():
        article = row["filepath"]

        title = None
        if article in articleset:
            continue
        articleset.add(article)
        with open(article, "r") as inputfile:
            creation_time = row["first"]
            time = row["latest"]
            content = inputfile.read()
            parsed_html = BeautifulSoup(content, features="html.parser")
            for link in parsed_html.find_all("title"):
                title = replace_name(link.text)
                title = title.strip()
                # display modification date of article along with the title
                for lang in ["en", "fr", "hi", "pa", "ml"]:
                    if article.startswith(lang):
                        articlelist[lang] = (
                            articlelist[lang]
                            + "\n<li property='itemListElement' typeof='ListItem'>"
                            + '<meta typeof="ListItem" property="position" content="'
                            + str(count[lang])
                            + '"/>'
                            + "<a property='item' typeof='WebPage' href='../"
                            + article
                            + "'>"
                            + "<span property='name'>"
                            + title
                            + "</span></a>"
                            + " <span class='date'>("
                            + datetime.fromtimestamp(creation_time).strftime("%d %B %Y")
                            + ";</span>"
                            + " <span class='date'>"
                            + datetime.fromtimestamp(time).strftime("%d %B %Y")
                            + ")</span></li>"
                        )
                        count[lang] = count[lang] + 1
                        break
                fe = fg.add_entry(order="append")
                fe.id("https://johnsamuel.info/" + article.strip())
                fe.title(title.strip())
                fe.pubDate(
                    datetime.fromtimestamp(time, tz=timezone("Europe/Amsterdam"))
                )
                fe.description(title)
                fe.link(href="https://johnsamuel.info/" + article.strip())

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
    rssfeed = fg.rss_str(pretty=True)
    fg.atom_file("atom.xml")
    fg.rss_file("rss.xml")


if len(sys.argv) > 1:
    print("The program takes no input")
    exit(1)

check_for_modified_articles()
