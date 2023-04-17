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
from analyse import HTMLTextAnalysis, WebsiteAnalysis
import pandas
import numpy as np


class Blog:
    @staticmethod
    def replace_name(title):
        title = title.replace(": John Samuel", "")
        title = title.replace(": ജോൺ ശമൂവേൽ", "")
        title = title.replace(": ਜੌਨ ਸੈਮੂਅਲ", "")
        title = title.replace(": जॉन शमुऐल", "")
        return title

    @staticmethod
    def generate_feed_from_dataframe(feed_df, feed_count=10, directory=""):
        articleset = set()
        fg = FeedGenerator()
        fg.id("https://johnsamuel.info")
        fg.title("John Samuel")
        fg.description("Personal Blog of John Samuel")
        fg.author({"name": "John Samuel"})
        fg.language("en")
        fg.link(href="https://johnsamuel.info")
        count = {}
        for lang in WebsiteAnalysis.get_languages():
            count[lang] = 1
        for index, row in feed_df.iterrows():
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
                    title = Blog.replace_name(link.text)
                    title = title.strip()
                    fe = fg.add_entry(order="append")
                    fe.id("https://johnsamuel.info/" + article.strip())
                    fe.title(title.strip())
                    fe.pubDate(
                        datetime.fromtimestamp(time, tz=timezone("Europe/Amsterdam"))
                    )
                    fe.description(title)
                    fe.link(href="https://johnsamuel.info/" + article.strip())

        # Writing the feed
        atomfeed = fg.atom_str(pretty=True)
        rssfeed = fg.rss_str(pretty=True)

        fg.atom_file(directory + "atom.xml", pretty=True)
        fg.rss_file(directory + "rss.xml", pretty=True)

    @staticmethod
    def generate_main_feed(dataframe, feed_count=10):
        df = dataframe.sort_values(["latest"], ascending=False).head(feed_count)
        Blog.generate_feed_from_dataframe(df, feed_count)

    @staticmethod
    def generate_feed_in_multiple_languages(dataframe, feed_count=10):
        for lang in WebsiteAnalysis.get_languages():
            lang_df = dataframe[dataframe["language"] == lang]
            lang_df = lang_df.sort_values(["latest"], ascending=False).head(feed_count)
            Blog.generate_feed_from_dataframe(lang_df, feed_count, "" + lang + "/")

    @staticmethod
    def generate_feed(df, feed_count=10):
        Blog.generate_main_feed(df, feed_count)
        Blog.generate_feed_in_multiple_languages(df, feed_count)

    @staticmethod
    def generate_complete_list_of_articles(df):
        df = df.sort_values(
            ["latest", "first", "filepath"], ascending=[False, False, True]
        )
        articleset = set()
        count = {}
        articlelist = {}
        for lang in WebsiteAnalysis.get_languages():
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
                    title = Blog.replace_name(link.text)
                    title = title.strip()
                    # display modification date of article along with the title
                    for lang in WebsiteAnalysis.get_languages():
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
                                + datetime.fromtimestamp(creation_time).strftime(
                                    "%d %B %Y"
                                )
                                + ";</span>"
                                + " <span class='date'>"
                                + datetime.fromtimestamp(time).strftime("%d %B %Y")
                                + ")</span></li>"
                            )
                            count[lang] = count[lang] + 1
                            break

        for lang in WebsiteAnalysis.get_languages():
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
        language_blog_list = {
            "EnglishArticleList": "en/blog.html",
            "FrenchArticleList": "fr/blog.html",
            "MalayalamArticleList": "ml/ബ്ലോഗ്.html",
            "HindiArticleList": "hi/ब्लॉग.html",
            "PunjabiArticleList": "pa/ਬਲਾਗ.html",
        }
        for language_article_list, blog_filepath in language_blog_list.items():
            language = blog_filepath[:2]
            with open("templates/blog/" + language + ".html", "r") as blogtemplate:
                content = blogtemplate.read()
                content = content.replace(language_article_list, articlelist[language])
                with open(blog_filepath, "w") as blog:
                    blog.write(content)
                blog.close()
            blogtemplate.close()

    @staticmethod
    def publish_report(article_list_df):
        token_filepath_set = set()
        for index, row in article_list_df.iterrows():
            tokens = HTMLTextAnalysis.get_tokens(
                row["filepath"],
                lowercase=True,
                remove_punctuation=True,
                remove_stopwords=True,
            )
            for token in tokens:
                token_filepath_set.add(
                    (token[0], token, row["language"], row["filepath"])
                )
        tf = pandas.DataFrame(
            token_filepath_set, columns=["first_char", "token", "language", "filepath"]
        )
        lang_articles = tf[["language", "filepath"]]
        lang_articles = lang_articles.drop_duplicates()
        lang_articles.groupby(["language"]).count()

        lang_articles_count = lang_articles.groupby(["language"]).count()
        lang_articles_count = lang_articles_count.reset_index()

        lang_words = tf[["language", "token"]]
        lang_words = lang_words.drop_duplicates()
        lang_words_count = lang_words.groupby(["language"]).count()
        lang_words_count = lang_words_count.reset_index()

        languages = {
            "en": "English",
            "fr": "French",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "hi": "Hindi",
        }
        with open("templates/report.html", "r") as blogtemplate:
            content = blogtemplate.read()
            for code, name in languages.items():
                content = content.replace(
                    name + "Articles",
                    str(
                        lang_articles_count[lang_articles_count["language"] == code][
                            "filepath"
                        ].values[0]
                    ),
                )
            for code, name in languages.items():
                content = content.replace(
                    name + "Words",
                    str(
                        lang_words_count[lang_words_count["language"] == code][
                            "token"
                        ].values[0]
                    ),
                )
            with open("blog/report.html", "w") as blog:
                blog.write(content)
            blog.close()

        blogtemplate.close()

        # Writing the report to the CSV file
        tf = tf.sort_values(["language", "first_char", "token", "filepath"])
        tf.to_csv("blog/report.csv", index=False)

    @staticmethod
    def generate_feed_and_complete_article_list():
        df = WebsiteAnalysis.get_articles_list_dataframe()
        Blog.generate_complete_list_of_articles(df)
        Blog.generate_feed(df, 20)
        Blog.publish_report(df)


if len(sys.argv) > 1:
    print("The program takes no input")
    exit(1)

# Generate the feed of last 10 articles
Blog.generate_feed_and_complete_article_list()
