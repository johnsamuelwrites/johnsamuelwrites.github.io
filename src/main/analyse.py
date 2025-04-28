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
from git import get_first_latest_modification
import os
import pandas

# Download the stopwords
# import nltk
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
        "en/research/art",
        "en/research/color",
        "en/research/3d",
        "en/research/games",
        "en/teaching/courses/2017/ArchitectureInformationSystems",
        "en/teaching/courses/2017/BigData",
        "en/teaching/courses/2017/C",
        "en/teaching/courses/2017/DataMining",
        "en/teaching/courses/2017/InternetTechnologyLanguage",
        "en/teaching/courses/2018/AITL",
        "en/teaching/courses/2018/Algorithms",
        "en/teaching/courses/2018/ArchitectureInformationSystems",
        "en/teaching/courses/2018/BigData",
        "en/teaching/courses/2018/C",
        "en/teaching/courses/2018/DataMining",
        "en/teaching/courses/2018/InternetTechnologyLanguage",
        "en/teaching/courses/2019/Algorithms",
        "en/teaching/courses/2019/ArchitectureInformationSystems",
        "en/teaching/courses/2019/BigData",
        "en/teaching/courses/2019/C",
        "en/teaching/courses/2019/DataMining",
        "en/teaching/courses/2019/InternetTechnologyLanguage",
        "en/teaching/courses/2019/MachineLearning",
        "en/teaching/courses/2019/SysProg",
        "en/teaching/courses/2020/Algorithms",
        "en/teaching/courses/2020/BigData",
        "en/teaching/courses/2020/C",
        "en/teaching/courses/2020/DataMining",
        "en/teaching/courses/2020/InternetTechnologyLanguage",
        "en/teaching/courses/2020/MachineLearning",
        "en/teaching/courses/2020/MDP",
        "en/teaching/courses/2020/SysProg",
        "en/teaching/courses/2021/Algorithms",
        "en/teaching/courses/2021/BigData",
        "en/teaching/courses/2021/C",
        "en/teaching/courses/2021/DataMining",
        "en/teaching/courses/2021/InternetTechnologyLanguage",
        "en/teaching/courses/2021/MachineLearning",
        "en/teaching/courses/2021/MDP",
        "en/teaching/courses/2021/SysProg",
        "en/teaching/courses/2022/AI-DeepLearning",
        "en/teaching/courses/2022/Algorithms",
        "en/teaching/courses/2022/C",
        "en/teaching/courses/2022/CN",
        "en/teaching/courses/2022/DataMining",
        "en/teaching/courses/2022/DP",
        "en/teaching/courses/2022/InternetTechnologyLanguage",
        "en/teaching/courses/2022/MachineLearning",
        "en/teaching/courses/2022/MDP",
        "en/teaching/courses/2022/SysProg",
        "en/teaching/courses/2023/AI-DeepLearning",
        "en/teaching/courses/2023/Algorithms",
        "en/teaching/courses/2023/C",
        "en/teaching/courses/2023/DataScience",
        "en/teaching/courses/2023/DataMining",
        "en/teaching/courses/2023/DP",
        "en/teaching/courses/2023/MachineLearning",
        "en/teaching/courses/2023/MDP",
        "en/teaching/courses/2023/DS4C",
        "en/teaching/courses/2024/PPL",
        "en/teaching/courses/2024/C",
        "en/teaching/courses/2024/DataScience",
        "en/teaching/courses/2024/DataMining",
        "en/teaching/courses/2024/DP",
        "en/teaching/courses/2024/MachineLearning",
        "en/teaching/courses/2024/MDP",
        "en/teaching/courses/2024/DS4C",
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
        "en/slides/2021/WikiWorkshop",
        "en/slides/2022/QueeringWikipedia",
        "en/slides/2023/CollectifArchivesLGBTQI+",
        "en/slides/2023/SASSQueer",
        "en/slides/2023/QueeringWikipedia",
        "en/slides/2024/CampusduLibre",
        "en/slides/2025/FOSDEM",
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
        "fr/recherche",
        "fr/enseignement/cours/2017/ArchitectureSystemeInformation",
        "fr/enseignement/cours/2017/BigData",
        "fr/enseignement/cours/2017/C",
        "fr/enseignement/cours/2017/CN",
        "fr/enseignement/cours/2017/DataMining",
        "fr/enseignement/cours/2017/TLI",
        "fr/enseignement/cours/2017/TLIA",
        "fr/enseignement/cours/2018/Algorithmes",
        "fr/enseignement/cours/2018/ArchitectureSystemeInformation",
        "fr/enseignement/cours/2018/BigData",
        "fr/enseignement/cours/2018/C",
        "fr/enseignement/cours/2018/CN",
        "fr/enseignement/cours/2018/DataMining",
        "fr/enseignement/cours/2018/TLI",
        "fr/enseignement/cours/2018/TLIA",
        "fr/enseignement/cours/2019/Algorithmes",
        "fr/enseignement/cours/2019/ArchitectureSystemeInformation",
        "fr/enseignement/cours/2019/BigData",
        "fr/enseignement/cours/2019/C",
        "fr/enseignement/cours/2019/DataMining",
        "fr/enseignement/cours/2019/MachineLearning",
        "fr/enseignement/cours/2019/ProgSys",
        "fr/enseignement/cours/2019/TLI",
        "fr/enseignement/cours/2020/Algorithmes",
        "fr/enseignement/cours/2020/BigData",
        "fr/enseignement/cours/2020/C",
        "fr/enseignement/cours/2020/DataMining",
        "fr/enseignement/cours/2020/MachineLearning",
        "fr/enseignement/cours/2020/ProgSys",
        "fr/enseignement/cours/2020/TDM",
        "fr/enseignement/cours/2020/TLI",
        "fr/enseignement/cours/2021/Algorithmes",
        "fr/enseignement/cours/2021/BigData",
        "fr/enseignement/cours/2021/C",
        "fr/enseignement/cours/2021/DataMining",
        "fr/enseignement/cours/2021/MachineLearning",
        "fr/enseignement/cours/2021/ProgSys",
        "fr/enseignement/cours/2021/TDM",
        "fr/enseignement/cours/2021/TLI",
        "fr/enseignement/cours/2021/DP",
        "fr/enseignement/cours/2022/Algorithmes",
        "fr/enseignement/cours/2022/C",
        "fr/enseignement/cours/2022/CN",
        "fr/enseignement/cours/2022/DataMining",
        "fr/enseignement/cours/2022/DP",
        "fr/enseignement/cours/2022/IA-DeepLearning",
        "fr/enseignement/cours/2022/MachineLearning",
        "fr/enseignement/cours/2022/ProgSys",
        "fr/enseignement/cours/2022/TDM",
        "fr/enseignement/cours/2022/TLI",
        "fr/enseignement/cours/2023/Algorithmes",
        "fr/enseignement/cours/2023/C",
        "fr/enseignement/cours/2023/DataScience",
        "fr/enseignement/cours/2023/DataMining",
        "fr/enseignement/cours/2023/DP",
        "fr/enseignement/cours/2023/IA-DeepLearning",
        "fr/enseignement/cours/2023/MachineLearning",
        "fr/enseignement/cours/2023/TDM",
        "fr/enseignement/cours/2024/PLP",
        "fr/enseignement/cours/2024/C",
        "fr/enseignement/cours/2024/DataScience",
        "fr/enseignement/cours/2024/DataMining",
        "fr/enseignement/cours/2024/DP",
        "fr/enseignement/cours/2024/IA-DeepLearning",
        "fr/enseignement/cours/2024/MachineLearning",
        "fr/enseignement/cours/2024/TDM",
    ]

    directories["ml"] = [
        "ml",
        "ml/അദ്ധ്യാപനം",
        "ml/ഗവേഷണം",
        "ml/ഭാഷാശാസ്ത്രം",
        "ml/യാത്രകൾ",
        "ml/രചനകൾ",
    ]

    directories["hi"] = [
        "hi",
        "hi/अध्यापन",
        "hi/अनुसंधान",
        "hi/भाषाविज्ञान",
        "hi/यात्रा",
        "hi/रचनायें",
    ]

    directories["pa"] = [
        "pa",
        "pa/ਅਧਿਆਪਨ",
        "pa/ਖੋਜ",
        "pa/ਭਾਸ਼ਾ ਵਿਗਿਆਨ",
        "pa/ਯਾਤਰਾ",
        "pa/ਲਿਖਤਾਂ",
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

    def get_directories():
        return WebsiteAnalysis.directories

    def get_languages():
        return ["en", "fr", "hi", "pa", "ml"]

    def get_excluded_files():
        return WebsiteAnalysis.exclude_files

    def get_articles_list_dataframe(main_directory=""):
        article_metadata = []
        directories = WebsiteAnalysis.get_directories()
        for language in directories:
            for directory in directories[language]:
                try:
                    filepath = None
                    for filename in os.listdir(main_directory + directory):
                        if ".html" not in filename:
                            continue
                        filepath = directory + "/" + filename
                        complete_filepath = main_directory + directory + "/" + filename
                        if (
                            os.path.isfile(complete_filepath)
                            and filepath not in WebsiteAnalysis.get_excluded_files()
                        ):
                            with open(complete_filepath, "r") as f:
                                if "NOTE: Article in Progress" not in f.read():
                                    first, latest = get_first_latest_modification(
                                        filepath, main_directory
                                    )
                                    article_metadata.append(
                                        [
                                            main_directory + filepath,
                                            language,
                                            first,
                                            latest,
                                        ]
                                    )

                except Exception as e:
                    print("Error: in file: " + filepath + ": " + str(e))

        df = pandas.DataFrame(
            article_metadata, columns=["filepath", "language", "first", "latest"]
        )
        df = df.sort_values(["latest", "first"], ascending=[False, False])
        return df


class HTMLTextAnalysis:
    @staticmethod
    def get_sentences_with_tokens(
        filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False
    ):
        sentences = []
        stopwords_set = set(stopwords.words("english"))
        with open(filepath, "r") as inputfile:
            content = inputfile.read()
            parsed_html = BeautifulSoup(content, features="html.parser")

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
    def get_tokens(
        filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False
    ):
        tokens = []
        stopwords_set = set(stopwords.words("english"))
        with open(filepath, "r") as inputfile:
            content = inputfile.read()
            parsed_html = BeautifulSoup(content, features="html.parser")

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
    def get_distinct_tokens(
        filepath, lowercase=True, remove_punctuation=False, remove_stopwords=False
    ):
        tokens = HTMLTextAnalysis.get_tokens(filepath, lowercase)
        distinct_tokens = list(set(tokens))
        return distinct_tokens

    @staticmethod
    def get_ngrams(article, n=2):
        tokens = HTMLTextAnalysis.get_tokens(article, False, True, True)
        ngrams_list = ngrams(tokens, n)
        return ngrams_list

    @staticmethod
    def get_ngrams_frequency(article, n=2):
        tokens = HTMLTextAnalysis.get_tokens(article, False, True, True)
        ngrams_list = ngrams(tokens, n)
        frequency = Counter(ngrams_list)
        return frequency


class WordEmbedding:
    @staticmethod
    def get_word2vec_model_from_sentences(sentences, skipgram=False):
        """By default, this approach uses CBOW model"""
        model = None
        if skipgram:
            model = Word2Vec(
                sentences=sentences,
                vector_size=100,
                window=2,
                min_count=1,
                workers=4,
                sg=1,
            )
        else:
            model = Word2Vec(
                sentences=sentences, vector_size=100, window=2, min_count=1, workers=4
            )
        return model

    @staticmethod
    def get_word2vec_model_from_HTMLfile(article, skipgram=False):
        sentences = HTMLTextAnalysis.get_sentences_with_tokens(
            article, False, True, True
        )
        model = WordEmbedding.get_word2vec_model_from_sentences(sentences, skipgram)
        return model
