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
