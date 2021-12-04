#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize, word_tokenize
from gensim.models import Word2Vec, Phrases
from nltk.corpus import stopwords
from nltk.util import ngrams
from collections import Counter

# Download the stopwords
#import nltk
# nltk.download('stopwords')

class WebsiteAnalysis:
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
        "en/slides/2020/DebConf",
        "en/slides/2020/DublinCoreMeeting",
        "en/slides/2020/EUvsVirus",
        "en/slides/2021/ContribuLing",
        "en/slides/2021/DCMIVirtual",
        "en/slides/2021/OpenSym",
        "en/slides/2021/WikidataCon",
        "en/slides/2021/WikiWorkshop"
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

class HTMLTextAnalysis:
    @staticmethod
    def get_sentences_with_tokens(filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False):
        sentences = []
        stopwords_set = set(stopwords.words('english'))
        with open(filepath, "r") as inputfile:
            content = inputfile.read()
            parsed_html = BeautifulSoup(content, features='html.parser')

            text = parsed_html.body.get_text()
            for sentence in sent_tokenize(text):
                token_list = []
                for token in word_tokenize(sentence):
                    if remove_punctuation and not token.isalnum():
                        continue
                    if remove_stopwords and (token in stopwords_set):
                        continue
                    if lowercase:
                        token_list.append(token.lower())
                    else:
                        token_list.append(token)
                sentences.append(token_list)
        return sentences

    @staticmethod
    def get_tokens(filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False):
        tokens = []
        stopwords_set = set(stopwords.words('english'))
        with open(filepath, "r") as inputfile:
            content = inputfile.read()
            parsed_html = BeautifulSoup(content, features='html.parser')

            text = parsed_html.body.get_text()
            for sentence in sent_tokenize(text):
                for token in word_tokenize(sentence):
                    if remove_punctuation and not token.isalnum():
                        continue
                    if remove_stopwords and token in stopwords_set:
                        continue
                    if lowercase:
                        tokens.append(token.lower())
                    else:
                        tokens.append(token)
        return tokens

    @staticmethod
    def get_distinct_tokens(filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False):
        tokens = HTMLTextAnalysis.get_tokens(filepath, lowercase)
        distinct_tokens = list(set(tokens))
        return(distinct_tokens)

    @staticmethod
    def get_ngrams(article, n=2):
        tokens = HTMLTextAnalysis.get_tokens(article, False, True, True)
        ngrams_list = ngrams(tokens, n)
        return (ngrams_list)

    @staticmethod
    def get_ngrams_frequency(article, n=2):
        tokens = HTMLTextAnalysis.get_tokens(article, False, True, True)
        ngrams_list = ngrams(tokens, n)
        frequency = Counter(ngrams_list)
        return (frequency)


class WordEmbedding:
    @staticmethod
    def get_word2vec_model_from_sentences(sentences, skipgram=False):
        """By default, this approach uses CBOW model
        """
        model = None
        if skipgram:
            model = Word2Vec(sentences=sentences, vector_size=100,
                             window=2, min_count=1, workers=4, sg=1)
        else:
            model = Word2Vec(sentences=sentences, vector_size=100,
                             window=2, min_count=1, workers=4)
        return model

    @staticmethod
    def get_word2vec_model_from_HTMLfile(article, skipgram=False):
        sentences = HTMLTextAnalysis.get_sentences_with_tokens(
            article, False, True, True)
        model = WordEmbedding.get_word2vec_model_from_sentences(
            sentences, skipgram)
        return model
