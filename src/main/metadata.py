#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Add, update and extract metadata (RDFa, JSON-LD, microdata) of a web page

from __future__ import annotations

import argparse
import json
import pprint
from datetime import datetime
from pathlib import Path
from typing import Sequence

import regex
from bs4 import BeautifulSoup

from config import SITE_AUTHOR, SITE_URL
from file_rewrite import rewrite_text_file
from paths import repo_url_for
from site_text import strip_author_from_title

JSONLD_TEMPLATE = """
{
    "@context" : "http://schema.org",
    "@type" : "BlogPosting",
    "mainEntityOfPage": {
         "@type": "WebPage",
         "@id": "https://johnsamuel.info"
    },
    "articleSection" : "blog",
    "name" : "",
    "headline" : "",
    "description" : "",
    "inLanguage" : "en",
    "author" : "John Samuel",
    "datePublished": "",
    "dateModified" : "",
    "dateCreated" : "",
    "url" : "",
    "image": {
       "@type": "imageObject",
       "url": "https://johnsamuel.info/images/writings/coconut-trees-landscape.svg",
       "height": "600",
       "width": "800"
    },
    "publisher": {
       "@type": "Organization",
       "name": "John Samuel",
       "logo": {
         "@type": "imageObject",
         "url": "https://johnsamuel.info/images/writings/coconut-trees-landscape.svg"
       }
    },
    "keywords" : ["Blog" ]
}
"""

JSONLD_SCRIPT_PATTERN = r'<script type="application\/ld\+json">(\n|.)*script>'


def replace_name(title: str) -> str:
    """Remove author names from a title."""
    return strip_author_from_title(title)


def get_article_content(link: str) -> str:
    """Read an HTML file from disk."""
    return Path(link).read_text(encoding="utf-8")


def get_title(html_content: str) -> str:
    """Extract the title text from an HTML document."""
    parsed_html = BeautifulSoup(html_content, features="html.parser")
    title = ""
    for title_tag in parsed_html.find_all("title"):
        title = replace_name(title_tag.text)
    return title


def get_title_from_link(link: str) -> str:
    """Extract the title from a file path."""
    content = get_article_content(link)
    return get_title(content)


def render_jsonld_script(payload: dict) -> str:
    """Render JSON-LD as a script tag."""
    return (
        '<script type="application/ld+json">\n      '
        + json.dumps(payload)
        + "\n    </script>"
    )


def resolve_file_timestamps(link: str) -> tuple[float, float]:
    """Resolve creation and modification timestamps, falling back to file metadata."""
    try:
        from git import get_first_latest_modification

        return get_first_latest_modification(link)
    except (ImportError, ModuleNotFoundError):
        file_path = Path(link)
        stat_result = file_path.stat()
        created = getattr(stat_result, "st_ctime", stat_result.st_mtime)
        return created, stat_result.st_mtime


def update_metadata_content(content: str, link: str) -> str:
    """Inject or replace JSON-LD metadata in an HTML document."""
    jsonld = json.loads(JSONLD_TEMPLATE)
    first, latest = resolve_file_timestamps(link)
    title = get_title(content)

    jsonld["dateCreated"] = str(datetime.fromtimestamp(first))
    jsonld["datePublished"] = str(datetime.fromtimestamp(first))
    jsonld["dateModified"] = str(datetime.fromtimestamp(latest))
    jsonld["name"] = title
    jsonld["description"] = f"Article by {SITE_AUTHOR}"
    jsonld["url"] = f"{SITE_URL}/{repo_url_for(link)}"
    jsonld["headline"] = title

    script_jsonld = render_jsonld_script(jsonld)
    if "application/ld+json" not in content:
        return content.replace("</head>", script_jsonld + "\n  </head>")
    return regex.sub(JSONLD_SCRIPT_PATTERN, script_jsonld, content)


def add_update_metadata(links: Sequence[str]) -> None:
    """Inject or update JSON-LD metadata for local HTML files."""
    for link in links:
        if link.startswith("http"):
            continue
        rewrite_text_file(
            link,
            lambda original_content, current_link=link: update_metadata_content(
                original_content, current_link
            ),
        )


def extract_metadata(links: Sequence[str], allow_remote: bool = False) -> None:
    """Extract metadata from local HTML files or, optionally, remote URLs."""
    import extruct

    for link in links:
        print("=======" + link + "========")
        pretty_printer = pprint.PrettyPrinter(indent=2)
        if link.startswith("http"):
            import requests
            from w3lib.html import get_base_url

            if not allow_remote:
                raise ValueError(
                    "Remote URL extraction is disabled by default. Use --allow-remote to enable it."
                )
            response = requests.get(link, timeout=10)
            response.raise_for_status()
            base_url = get_base_url(response.text, response.url)
            data = extruct.extract(response.text, base_url=base_url)
        else:
            data = extruct.extract(Path(link).read_text(encoding="utf-8"))
        pretty_printer.pprint(data)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Set or extract metadata from a URL or an HTML file."
    )
    subparsers = parser.add_subparsers(help="sub-command help", dest="subparser_name")

    parser_extract = subparsers.add_parser("extract", help="extract metadata")
    parser_extract.add_argument(
        "link", metavar="link", type=str, nargs="+", help="link or paths of html file"
    )
    parser_extract.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow metadata extraction from remote HTTP URLs.",
    )

    parser_add = subparsers.add_parser("add", help="add metadata")
    parser_add.add_argument(
        "link", metavar="link", type=str, nargs="+", help="link or paths of html file"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subparser_name == "extract":
        extract_metadata(args.link, allow_remote=args.allow_remote)
        return 0
    if args.subparser_name == "add":
        add_update_metadata(args.link)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
