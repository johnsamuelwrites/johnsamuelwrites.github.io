#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize, word_tokenize
from gensim.models import Word2Vec
from nltk.corpus import stopwords
from nltk.util import ngrams
from collections import Counter
from git import get_first_latest_modification
import os
from pathlib import Path
import pandas

# Download the stopwords
# import nltk
# nltk.download('stopwords')


class WebsiteAnalysis:
    """Analyzes website content across multiple languages and directories."""

    # Supported languages for the website
    SUPPORTED_LANGUAGES = ["en", "fr", "hi", "pa", "ml"]

    # Root directories for each language
    LANGUAGE_ROOTS = {
        "en": "en",
        "fr": "fr",
        "ml": "ml",
        "hi": "hi",
        "pa": "pa",
    }

    # Files to exclude from analysis (relative paths from main_directory)
    EXCLUDE_FILES = {
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

    @staticmethod
    def get_languages():
        """Return list of supported languages."""
        return WebsiteAnalysis.SUPPORTED_LANGUAGES

    @staticmethod
    def get_excluded_files():
        """Return set of excluded file paths."""
        return WebsiteAnalysis.EXCLUDE_FILES

    @staticmethod
    def _find_html_files(root_dir, language_root, main_directory=""):
        """
        Recursively find all HTML files under a language root directory.

        Args:
            root_dir: Absolute path to the language root directory
            language_root: Relative path from main_directory (e.g., "en", "fr")
            main_directory: Base directory path

        Yields:
            Tuples of (relative_filepath, absolute_filepath, language)
        """
        try:
            for root, dirs, files in os.walk(root_dir):
                # Calculate relative path from main_directory
                rel_root = os.path.relpath(root, main_directory)

                for filename in files:
                    if not filename.endswith(".html"):
                        continue

                    # Construct paths
                    rel_filepath = os.path.join(rel_root, filename)
                    abs_filepath = os.path.join(root, filename)

                    # Normalize path separators for consistent comparison
                    rel_filepath = rel_filepath.replace(os.sep, "/")

                    # Skip excluded files
                    if rel_filepath in WebsiteAnalysis.EXCLUDE_FILES:
                        continue

                    # Determine language from the root path
                    language = language_root.split("/")[0]

                    yield rel_filepath, abs_filepath, language

        except (OSError, PermissionError) as e:
            print(f"Warning: Could not access directory {root_dir}: {e}")

    @staticmethod
    def get_articles_list_dataframe(main_directory=""):
        """
        Recursively scan all language directories for HTML articles.

        Args:
            main_directory: Base directory path (can be empty for current directory)

        Returns:
            pandas.DataFrame with columns: filepath, language, first, latest
        """
        article_metadata = []

        # Ensure main_directory ends with separator if not empty
        if main_directory and not main_directory.endswith(os.sep):
            main_directory += os.sep

        # Process each language root directory
        for language, language_root in WebsiteAnalysis.LANGUAGE_ROOTS.items():
            root_dir = (
                os.path.join(main_directory, language_root)
                if main_directory
                else language_root
            )

            # Skip if directory doesn't exist
            if not os.path.isdir(root_dir):
                print(f"Warning: Language root directory not found: {root_dir}")
                continue

            # Find and process all HTML files
            for rel_filepath, abs_filepath, lang in WebsiteAnalysis._find_html_files(
                root_dir, language_root, main_directory
            ):
                try:
                    # Check if file contains "Article in Progress" marker
                    with open(abs_filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "NOTE: Article in Progress" in content:
                            continue

                    # Get Git modification dates
                    first, latest = get_first_latest_modification(
                        rel_filepath, main_directory
                    )

                    article_metadata.append(
                        [
                            abs_filepath,
                            lang,
                            first,
                            latest,
                        ]
                    )

                except (OSError, UnicodeDecodeError) as e:
                    print(f"Error processing file {rel_filepath}: {e}")
                except Exception as e:
                    print(f"Unexpected error processing file {rel_filepath}: {e}")

        # Create and sort DataFrame
        df = pandas.DataFrame(
            article_metadata, columns=["filepath", "language", "first", "latest"]
        )
        df = df.sort_values(["latest", "first"], ascending=[False, False])

        return df


class HTMLTextAnalysis:
    """Provides text analysis utilities for HTML documents."""

    @staticmethod
    def _parse_html_text(filepath):
        """
        Extract text content from HTML file.

        Args:
            filepath: Path to HTML file

        Returns:
            Extracted text string or None if parsing fails
        """
        try:
            with open(filepath, "r", encoding="utf-8") as inputfile:
                content = inputfile.read()
                parsed_html = BeautifulSoup(content, features="html.parser")

                if parsed_html.body:
                    return parsed_html.body.get_text()
                else:
                    print(f"Warning: No body tag found in {filepath}")
                    return parsed_html.get_text()
        except Exception as e:
            print(f"Error parsing HTML from {filepath}: {e}")
            return None

    @staticmethod
    def get_sentences_with_tokens(
        filepath,
        lowercase=True,
        remove_punctuation=False,
        remove_stopwords=False,
        language="english",
    ):
        """
        Extract sentences as lists of tokens from HTML file.

        Args:
            filepath: Path to HTML file
            lowercase: Convert tokens to lowercase
            remove_punctuation: Remove non-alphanumeric tokens
            remove_stopwords: Remove common stopwords
            language: Language for stopwords (default: 'english')

        Returns:
            List of sentences, where each sentence is a list of tokens
        """
        sentences = []
        stopwords_set = set(stopwords.words(language)) if remove_stopwords else set()

        text = HTMLTextAnalysis._parse_html_text(filepath)
        if not text:
            return sentences

        for sentence in sent_tokenize(text):
            token_list = []
            for token in word_tokenize(sentence):
                # Apply filters
                if remove_punctuation and not token.isalnum():
                    continue
                if remove_stopwords and token.lower() in stopwords_set:
                    continue

                # Apply case transformation
                token_list.append(token.lower() if lowercase else token)

            if token_list:  # Only add non-empty sentences
                sentences.append(token_list)

        return sentences

    @staticmethod
    def get_tokens(
        filepath,
        lowercase=True,
        remove_punctuation=False,
        remove_stopwords=False,
        language="english",
    ):
        """
        Extract all tokens from HTML file.

        Args:
            filepath: Path to HTML file
            lowercase: Convert tokens to lowercase
            remove_punctuation: Remove non-alphanumeric tokens
            remove_stopwords: Remove common stopwords
            language: Language for stopwords (default: 'english')

        Returns:
            List of tokens
        """
        tokens = []
        stopwords_set = set(stopwords.words(language)) if remove_stopwords else set()

        text = HTMLTextAnalysis._parse_html_text(filepath)
        if not text:
            return tokens

        for sentence in sent_tokenize(text):
            for token in word_tokenize(sentence):
                # Apply filters
                if remove_punctuation and not token.isalnum():
                    continue
                if remove_stopwords and token.lower() in stopwords_set:
                    continue

                # Apply case transformation
                tokens.append(token.lower() if lowercase else token)

        return tokens

    @staticmethod
    def get_distinct_tokens(
        filepath,
        lowercase=True,
        remove_punctuation=False,
        remove_stopwords=False,
        language="english",
    ):
        """
        Extract unique tokens from HTML file.

        Args:
            filepath: Path to HTML file
            lowercase: Convert tokens to lowercase
            remove_punctuation: Remove non-alphanumeric tokens
            remove_stopwords: Remove common stopwords
            language: Language for stopwords (default: 'english')

        Returns:
            List of unique tokens
        """
        tokens = HTMLTextAnalysis.get_tokens(
            filepath, lowercase, remove_punctuation, remove_stopwords, language
        )
        return list(set(tokens))

    @staticmethod
    def get_ngrams(article, n=2):
        """
        Extract n-grams from HTML file.

        Args:
            article: Path to HTML file
            n: Size of n-grams (default: 2 for bigrams)

        Returns:
            Generator of n-gram tuples
        """
        tokens = HTMLTextAnalysis.get_tokens(
            article, lowercase=False, remove_punctuation=True, remove_stopwords=True
        )
        return ngrams(tokens, n)

    @staticmethod
    def get_ngrams_frequency(article, n=2):
        """
        Calculate frequency distribution of n-grams in HTML file.

        Args:
            article: Path to HTML file
            n: Size of n-grams (default: 2 for bigrams)

        Returns:
            Counter object with n-gram frequencies
        """
        ngrams_list = HTMLTextAnalysis.get_ngrams(article, n)
        return Counter(ngrams_list)


class WordEmbedding:
    """Provides word embedding utilities using Word2Vec."""

    @staticmethod
    def get_word2vec_model_from_sentences(
        sentences, skipgram=False, vector_size=100, window=2, min_count=1, workers=4
    ):
        """
        Train Word2Vec model from sentences.

        Args:
            sentences: List of sentences, where each sentence is a list of tokens
            skipgram: Use Skip-gram model if True, otherwise use CBOW (default: False)
            vector_size: Dimensionality of word vectors (default: 100)
            window: Maximum distance between current and predicted word (default: 2)
            min_count: Minimum word frequency threshold (default: 1)
            workers: Number of worker threads (default: 4)

        Returns:
            Trained Word2Vec model
        """
        if not sentences:
            raise ValueError("Cannot train model on empty sentences list")

        model = Word2Vec(
            sentences=sentences,
            vector_size=vector_size,
            window=window,
            min_count=min_count,
            workers=workers,
            sg=1 if skipgram else 0,
        )
        return model

    @staticmethod
    def get_word2vec_model_from_HTMLfile(
        article, skipgram=False, vector_size=100, window=2, min_count=1, workers=4
    ):
        """
        Train Word2Vec model from HTML file content.

        Args:
            article: Path to HTML file
            skipgram: Use Skip-gram model if True, otherwise use CBOW (default: False)
            vector_size: Dimensionality of word vectors (default: 100)
            window: Maximum distance between current and predicted word (default: 2)
            min_count: Minimum word frequency threshold (default: 1)
            workers: Number of worker threads (default: 4)

        Returns:
            Trained Word2Vec model
        """
        sentences = HTMLTextAnalysis.get_sentences_with_tokens(
            article, lowercase=False, remove_punctuation=True, remove_stopwords=True
        )

        return WordEmbedding.get_word2vec_model_from_sentences(
            sentences, skipgram, vector_size, window, min_count, workers
        )
