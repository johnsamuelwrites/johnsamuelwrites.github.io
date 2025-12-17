#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


# Generate an upto date list of articles in reverse chronological order
#!/usr/bin/env python3

import sys
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd
from feedgen.feed import FeedGenerator
from pytz import timezone

from analyse import HTMLTextAnalysis, WebsiteAnalysis
from git import get_first_latest_modification


@dataclass
class ArticleMetadata:
    """Rich metadata for a blog article."""

    filepath: str
    language: str
    title: str
    creation_time: int
    modification_time: int
    word_count: int
    reading_time: int  # minutes
    year: int
    is_recently_updated: bool = False

    @property
    def creation_date_str(self) -> str:
        """Formatted creation date."""
        return datetime.fromtimestamp(self.creation_time).strftime("%d %B %Y")

    @property
    def modification_date_str(self) -> str:
        """Formatted modification date."""
        return datetime.fromtimestamp(self.modification_time).strftime("%d %B %Y")

    @property
    def is_updated(self) -> bool:
        """Check if article was modified after creation."""
        # Allow for small time difference (1 day)
        return abs(self.modification_time - self.creation_time) > 86400


class BlogGenerator:
    """Enhanced blog generator with year-based organization."""

    # Words per minute reading speed
    READING_SPEED = 200

    # Recent update threshold (30 days)
    RECENT_UPDATE_THRESHOLD = 30 * 24 * 60 * 60

    @staticmethod
    def clean_title(title: str) -> str:
        """Remove author name variations from title."""
        replacements = [
            ": John Samuel",
            ": ജോൺ ശമൂവേൽ",
            ": ਜੌਨ ਸੈਮੂਅਲ",
            ": जॉन शमुऐल",
        ]
        for replacement in replacements:
            title = title.replace(replacement, "")
        return title.strip()

    @staticmethod
    def calculate_reading_time(word_count: int) -> int:
        """Calculate reading time in minutes."""
        minutes = max(1, round(word_count / BlogGenerator.READING_SPEED))
        return minutes

    @staticmethod
    def is_recently_updated(modification_time: int) -> bool:
        """Check if article was updated recently."""
        current_time = datetime.now().timestamp()
        return (
            current_time - modification_time
        ) < BlogGenerator.RECENT_UPDATE_THRESHOLD

    @staticmethod
    def extract_article_metadata(filepath: str) -> ArticleMetadata:
        """Extract comprehensive metadata from an article."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            parsed_html = BeautifulSoup(content, features="html.parser")

            # Extract title
            title_tag = parsed_html.find("title")
            title = (
                BlogGenerator.clean_title(title_tag.text) if title_tag else "Untitled"
            )

            # Get timestamps
            creation_time, modification_time = get_first_latest_modification(
                filepath, ""
            )

            # Determine language from filepath
            language = filepath.split("/")[0] if "/" in filepath else "en"

            # Calculate word count
            tokens = HTMLTextAnalysis.get_tokens(
                filepath,
                lowercase=True,
                remove_punctuation=True,
                remove_stopwords=False,
            )
            word_count = len(tokens)

            # Calculate reading time
            reading_time = BlogGenerator.calculate_reading_time(word_count)

            # Extract year
            year = datetime.fromtimestamp(creation_time).year

            # Check if recently updated
            is_recently_updated = BlogGenerator.is_recently_updated(modification_time)

            return ArticleMetadata(
                filepath=filepath,
                language=language,
                title=title,
                creation_time=creation_time,
                modification_time=modification_time,
                word_count=word_count,
                reading_time=reading_time,
                year=year,
                is_recently_updated=is_recently_updated,
            )

    @staticmethod
    def generate_article_html(article: ArticleMetadata, position: int) -> str:
        """Generate HTML for a single article entry."""
        updated_badge = ""
        if article.is_recently_updated:
            updated_badge = (
                '<span class="updated-badge" title="Recently Updated">🔥</span>'
            )

        modified_indicator = ""
        if article.is_updated:
            modified_indicator = (
                f'<span class="modified-date">{article.modification_date_str}</span>'
            )

        return f"""
            <li property='itemListElement' typeof='ListItem' class="article-item" data-year="{article.year}">
                <meta typeof="ListItem" property="position" content="{position}"/>
                <div class="article-main">
                    <a property='item' typeof='WebPage' href='../{article.filepath}' class="article-link">
                        <span property='name' class="article-title">{article.title}</span>
                    </a>
                    {updated_badge}
                </div>
                <div class="article-meta">
                    <span class="meta-item creation-date" title="Created">
                        <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" stroke-width="2"/>
                        </svg>
                        {article.creation_date_str}
                    </span>
                    {f'<span class="meta-item" title="Last Modified">→ {modified_indicator}</span>' if article.is_updated else ''}
                    <span class="meta-item reading-time" title="Reading Time">
                        <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="12" cy="12" r="10" stroke-width="2"/>
                            <path d="M12 6v6l4 2" stroke-width="2"/>
                        </svg>
                        {article.reading_time} min
                    </span>
                    <span class="meta-item word-count" title="Word Count">
                        <svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 014 17m0 2.5v-15A2.5 2.5 0 016.5 2H20v18H6.5A2.5 2.5 0 014 17" stroke-width="2"/>
                        </svg>
                        {article.word_count} words
                    </span>
                </div>
            </li>
        """

    @staticmethod
    def organize_articles_by_year(
        articles: List[ArticleMetadata],
    ) -> Dict[int, List[ArticleMetadata]]:
        """Organize articles by year."""
        articles_by_year: Dict[int, List[ArticleMetadata]] = {}
        for article in articles:
            if article.year not in articles_by_year:
                articles_by_year[article.year] = []
            articles_by_year[article.year].append(article)
        return articles_by_year

    @staticmethod
    def generate_year_section(
        year: int, articles: List[ArticleMetadata], start_position: int
    ) -> str:
        """Generate HTML for a year section."""
        article_count = len(articles)

        articles_html = ""
        for i, article in enumerate(articles):
            articles_html += BlogGenerator.generate_article_html(
                article, start_position + i
            )

        return f"""
            <div class="year-section" id="year-{year}">
                <div class="year-header">
                    <h3 class="year-title">{year}</h3>
                    <span class="year-count">{article_count} article{'s' if article_count != 1 else ''}</span>
                </div>
                <ul vocab='http://schema.org/' typeof='ItemList' class="article-list">
                    {articles_html}
                </ul>
            </div>
        """

    @staticmethod
    def generate_complete_list(df: pd.DataFrame) -> None:
        """Generate complete list of articles organized by year and language."""
        # Sort by modification date, then creation date, then filepath
        df = df.sort_values(
            ["latest", "first", "filepath"], ascending=[False, False, True]
        )

        # Extract metadata for all articles
        articleset: Set[str] = set()
        articles_by_language: Dict[str, List[ArticleMetadata]] = {
            lang: [] for lang in WebsiteAnalysis.get_languages()
        }

        for _, row in df.iterrows():
            if row["filepath"] in articleset:
                continue
            articleset.add(row["filepath"])

            try:
                metadata = BlogGenerator.extract_article_metadata(row["filepath"])
                if metadata.language in articles_by_language:
                    articles_by_language[metadata.language].append(metadata)
            except Exception as e:
                print(f"Error processing {row['filepath']}: {e}")
                continue

        # Generate main blog page (all languages)
        BlogGenerator._generate_multilingual_blog(articles_by_language)

        # Generate language-specific pages
        BlogGenerator._generate_language_specific_blogs(articles_by_language)

    @staticmethod
    def _generate_multilingual_blog(
        articles_by_language: Dict[str, List[ArticleMetadata]],
    ) -> None:
        """Generate the main multilingual blog page."""
        # Generate content for each language
        language_content = {}

        for lang_code in ["en", "fr", "ml", "pa", "hi"]:
            if (
                lang_code not in articles_by_language
                or not articles_by_language[lang_code]
            ):
                language_content[lang_code] = ""
                continue

            articles = articles_by_language[lang_code]

            # Sort by year descending, then by modification date descending
            articles.sort(key=lambda x: (x.year, x.modification_time), reverse=True)

            # Organize by year
            articles_by_year = BlogGenerator.organize_articles_by_year(articles)
            years = sorted(articles_by_year.keys(), reverse=True)

            # Generate year sections with proper wrapping
            year_sections = ""
            position = 1
            for year in years:
                year_articles = sorted(
                    articles_by_year[year],
                    key=lambda x: x.modification_time,
                    reverse=True,
                )
                year_sections += BlogGenerator.generate_year_section(
                    year, year_articles, position
                )
                position += len(year_articles)

            # Wrap in language section
            language_content[
                lang_code
            ] = f"""
                <section class="language-section" id="{lang_code}">
                    <div class="years-container">
                        {year_sections}
                    </div>
                </section>
            """

        # Read template
        template_path = Path("templates/blog.html")
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace each language placeholder individually
        content = content.replace("EnglishArticleList", language_content.get("en", ""))
        content = content.replace("FrenchArticleList", language_content.get("fr", ""))
        content = content.replace(
            "MalayalamArticleList", language_content.get("ml", "")
        )
        content = content.replace("PunjabiArticleList", language_content.get("pa", ""))
        content = content.replace("HindiArticleList", language_content.get("hi", ""))

        # Write the output
        output_path = Path("blog/index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _generate_multilingual_blog1(
        articles_by_language: Dict[str, List[ArticleMetadata]],
    ) -> None:
        """Generate the main multilingual blog page."""
        language_names = {
            "en": "English",
            "fr": "Français",
            "ml": "മലയാളം",
            "pa": "ਪੰਜਾਬੀ",
            "hi": "हिन्दी",
        }

        language_sections = ""
        for lang_code in ["en", "fr", "ml", "pa", "hi"]:
            if lang_code not in articles_by_language:
                continue

            articles = articles_by_language[lang_code]
            if not articles:
                continue

            # Sort by year descending, then by modification date descending
            articles.sort(key=lambda x: (x.year, x.modification_time), reverse=True)

            # Organize by year
            articles_by_year = BlogGenerator.organize_articles_by_year(articles)
            years = sorted(articles_by_year.keys(), reverse=True)

            year_sections = ""
            position = 1
            for year in years:
                year_articles = sorted(
                    articles_by_year[year],
                    key=lambda x: x.modification_time,
                    reverse=True,
                )
                year_sections += BlogGenerator.generate_year_section(
                    year, year_articles, position
                )
                position += len(year_articles)
                print(position)
                print(year_articles)
                language_sections += f"""
                <section class="language-section" id="{lang_code}">
                    <h2 class="language-title">{language_names[lang_code]}</h2>
                    <div class="years-container">
                        {year_sections}
                    </div>
                </section>
            """

        # Read template and replace content
        template_path = Path("templates/blog.html")
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace the placeholder with actual content
        content = content.replace(
            'EnglishArticleList\n            <h2 id="French">Français</h2>\n            FrenchArticleList\n            <h2 id="Malayalam">മലയാളം</h2>\n            MalayalamArticleList\n            <h2 id="Punjabi">ਪੰਜਾਬੀ</h2>\n            PunjabiArticleList\n            <h2 id="Hindi">हिन्दी</h2>\n            HindiArticleList',
            language_sections,
        )

        # Write the output
        output_path = Path("blog/index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _generate_language_specific_blogs(
        articles_by_language: Dict[str, List[ArticleMetadata]],
    ) -> None:
        """Generate language-specific blog pages."""
        language_configs = {
            "en": {"template": "templates/blog/en.html", "output": "en/blog.html"},
            "fr": {"template": "templates/blog/fr.html", "output": "fr/blog.html"},
            "ml": {"template": "templates/blog/ml.html", "output": "ml/ബ്ലോഗ്.html"},
            "pa": {"template": "templates/blog/pa.html", "output": "pa/ਬਲਾਗ.html"},
            "hi": {"template": "templates/blog/hi.html", "output": "hi/ब्लॉग.html"},
        }

        for lang_code, config in language_configs.items():
            if lang_code not in articles_by_language:
                continue

            articles = articles_by_language[lang_code]
            if not articles:
                continue

            # Sort by year descending, then by modification date descending
            articles.sort(key=lambda x: (x.year, x.modification_time), reverse=True)

            # Organize by year
            articles_by_year = BlogGenerator.organize_articles_by_year(articles)
            years = sorted(articles_by_year.keys(), reverse=True)

            year_sections = ""
            position = 1
            for year in years:
                year_articles = sorted(
                    articles_by_year[year],
                    key=lambda x: x.modification_time,
                    reverse=True,
                )
                year_sections += BlogGenerator.generate_year_section(
                    year, year_articles, position
                )
                position += len(year_articles)

            # Read template
            template_path = Path(config["template"])
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace placeholder
            content = content.replace("EnglishArticleList", year_sections)
            content = content.replace("FrenchArticleList", year_sections)
            content = content.replace("MalayalamArticleList", year_sections)
            content = content.replace("PunjabiArticleList", year_sections)
            content = content.replace("HindiArticleList", year_sections)

            # Write output
            output_path = Path(config["output"])
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

    @staticmethod
    def generate_feed(df: pd.DataFrame, feed_count: int = 20) -> None:
        """Generate RSS/Atom feeds (unchanged - latest N articles approach)."""
        # Sort by latest modification
        df = df.sort_values(["latest"], ascending=False).head(feed_count)

        articleset: Set[str] = set()
        fg = FeedGenerator()
        fg.id("https://johnsamuel.info")
        fg.title("John Samuel")
        fg.description("Personal Blog of John Samuel")
        fg.author({"name": "John Samuel"})
        fg.language("en")
        fg.link(href="https://johnsamuel.info")

        for _, row in df.iterrows():
            if row["filepath"] in articleset:
                continue
            articleset.add(row["filepath"])

            try:
                metadata = BlogGenerator.extract_article_metadata(row["filepath"])

                fe = fg.add_entry(order="append")
                fe.id(f"https://johnsamuel.info/{row['filepath']}")
                fe.title(metadata.title)
                fe.pubDate(
                    datetime.fromtimestamp(
                        metadata.modification_time, tz=timezone("Europe/Amsterdam")
                    )
                )
                fe.description(metadata.title)
                fe.link(href=f"https://johnsamuel.info/{row['filepath']}")
            except Exception as e:
                print(f"Error adding to feed {row['filepath']}: {e}")
                continue

        # Write feeds
        fg.atom_file("atom.xml", pretty=True)
        fg.rss_file("rss.xml", pretty=True)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        print("This program takes no input")
        sys.exit(1)

    # Get articles dataframe
    df = WebsiteAnalysis.get_articles_list_dataframe()

    # Generate complete article list with year organization
    BlogGenerator.generate_complete_list(df)

    # Generate feeds (latest N articles)
    BlogGenerator.generate_feed(df, feed_count=20)

    print("✓ Blog generation complete!")


if __name__ == "__main__":
    main()
