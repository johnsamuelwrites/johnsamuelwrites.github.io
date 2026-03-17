#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-language search index generator for the static website.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from config import CATEGORY_MAP, SUPPORTED_LANGUAGES
from manifest import BuildManifest
from paths import language_root, repo_root, search_index_path

# Set UTF-8 encoding for output (fixes Windows console issues)
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors="replace")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors="replace")


EXCLUDE_PATTERNS = [
    r"node_modules",
    r"search-index\.json$",
    r"search\.html$",
]


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML."""

    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.skip_tags = {"script", "style", "nav", "footer"}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            self.text.append(data)

    def get_text(self):
        return " ".join(self.text)


def get_all_html_files(directory: Path) -> list[Path]:
    """Get all HTML files recursively."""
    html_files: list[Path] = []
    for file_path in directory.rglob("*.html"):
        relative_path = str(file_path.relative_to(directory))
        excluded = any(re.search(pattern, relative_path) for pattern in EXCLUDE_PATTERNS)
        if not excluded:
            html_files.append(file_path)
    return html_files


def get_category(file_path: Path, base_dir: Path) -> str:
    """Determine category from file path."""
    relative_path = file_path.relative_to(base_dir)
    parts = relative_path.parts

    for key, value in CATEGORY_MAP.items():
        if parts[0] == key or key in str(relative_path):
            return value
    return "general"


def extract_title(html: str, file_path: Path) -> str:
    """Extract title from HTML."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        if title:
            return re.sub(r"<[^>]+>", "", title)

    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1_match:
        heading = h1_match.group(1).strip()
        if heading:
            return re.sub(r"<[^>]+>", "", heading)

    return file_path.stem.replace("-", " ").title()


def extract_description(html: str) -> str:
    """Extract meta description or first paragraph."""
    description_match = re.search(
        r"<meta\s+name=[\"']description[\"']\s+content=[\"']([^\"']+)[\"']",
        html,
        re.IGNORECASE,
    )
    if description_match:
        return description_match.group(1).strip()

    paragraph_match = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
    if paragraph_match:
        text = re.sub(r"<[^>]+>", "", paragraph_match.group(1))
        return text.strip()[:200]
    return ""


def extract_content(html: str) -> str:
    """Extract text content from HTML."""
    try:
        parser = HTMLTextExtractor()
        parser.feed(html)
        return re.sub(r"\s+", " ", parser.get_text()).strip()
    except Exception as error:
        print(f"Error extracting content: {error}")
        return ""


def process_file(file_path: Path, base_dir: Path) -> dict | None:
    """Process a single HTML file."""
    try:
        html = file_path.read_text(encoding="utf-8")
        relative_path = file_path.relative_to(base_dir)
        return {
            "url": "./" + str(relative_path).replace("\\", "/"),
            "title": extract_title(html, file_path),
            "description": extract_description(html),
            "content": extract_content(html)[:1000],
            "category": get_category(file_path, base_dir),
            "path": str(relative_path),
        }
    except Exception as error:
        print(f"Error processing {file_path}: {error}")
        return None


def build_search_index_for_language(lang_code: str, lang_name: str, force: bool = False):
    """Build a search index for a specific language."""
    base_dir = language_root(lang_code)
    output_file = search_index_path(lang_code)
    html_files = get_all_html_files(base_dir) if base_dir.exists() and base_dir.is_dir() else []
    manifest = BuildManifest()
    sources = [Path(__file__), *html_files]

    print(f"\n{'=' * 60}")
    print(f"Building search index for {lang_name} ({lang_code})")
    print(f"{'=' * 60}")
    print(f"Base directory: {base_dir}")

    if not base_dir.exists():
        print(f"[WARNING] Directory {base_dir} does not exist. Skipping.")
        return None
    if not base_dir.is_dir():
        print(f"[WARNING] {base_dir} is not a directory. Skipping.")
        return None

    print(f"Found {len(html_files)} HTML files")
    if not html_files:
        print("[WARNING] No HTML files found. Skipping.")
        return None

    if not force and manifest.is_current(f"search-index:{lang_code}", sources, [output_file]):
        print(f"[SKIP] Search index is up to date: {output_file}")
        file_size = output_file.stat().st_size
        return {
            "lang_code": lang_code,
            "lang_name": lang_name,
            "total_files": len(html_files),
            "processed": len(html_files),
            "output_file": str(output_file),
            "file_size": file_size,
            "categories": {},
        }

    index = []
    processed = 0
    for index_position, file_path in enumerate(html_files, start=1):
        entry = process_file(file_path, base_dir)
        if entry:
            index.append(entry)
            processed += 1
        if index_position % 50 == 0:
            print(f"Processed {index_position}/{len(html_files)} files...")

    print(f"Successfully processed {processed} files")
    output_file.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Search index written to: {output_file}")

    categories: dict[str, int] = {}
    for item in index:
        category = item["category"]
        categories[category] = categories.get(category, 0) + 1

    print("\nCategory breakdown:")
    for category, count in sorted(categories.items(), key=lambda item: item[1], reverse=True):
        print(f"  {category}: {count}")

    file_size = output_file.stat().st_size
    if file_size < 1024:
        size_str = f"{file_size} B"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size / (1024 * 1024):.1f} MB"

    print(f"\nIndex file size: {size_str}")
    manifest.update(f"search-index:{lang_code}", sources, [output_file])
    return {
        "lang_code": lang_code,
        "lang_name": lang_name,
        "total_files": len(html_files),
        "processed": processed,
        "output_file": str(output_file),
        "file_size": file_size,
        "categories": categories,
    }


def parse_args(argv=None):
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Build search indexes for one or more supported languages."
    )
    parser.add_argument(
        "languages",
        nargs="*",
        help="Optional language codes to build. Defaults to all supported languages.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate outputs even when the build manifest says they are current.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Main function to build search indexes for all languages."""
    args = parse_args(argv)
    requested_languages = args.languages or list(SUPPORTED_LANGUAGES.keys())
    invalid_languages = [
        language for language in requested_languages if language not in SUPPORTED_LANGUAGES
    ]
    if invalid_languages:
        print(f"Unknown language code(s): {', '.join(invalid_languages)}")
        return 1

    print("=" * 60)
    print("Multi-Language Search Index Generator")
    print("=" * 60)
    print(f"Repository root: {repo_root()}")
    print(f"Languages to process: {', '.join(requested_languages)}")

    results = {}
    for lang_code in requested_languages:
        result = build_search_index_for_language(
            lang_code,
            SUPPORTED_LANGUAGES[lang_code],
            force=args.force,
        )
        if result:
            results[lang_code] = result

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if not results:
        print("No search indexes were generated.")
        return 0

    total_files = sum(result["processed"] for result in results.values())
    total_size = sum(result["file_size"] for result in results.values())

    print(f"\n[SUCCESS] Generated {len(results)} search index(es)")
    print(f"Total pages indexed: {total_files}")

    if total_size < 1024 * 1024:
        size_str = f"{total_size / 1024:.1f} KB"
    else:
        size_str = f"{total_size / (1024 * 1024):.1f} MB"
    print(f"Total index size: {size_str}")

    print("\nLanguages processed:")
    for lang_code, result in results.items():
        print(f"  - {result['lang_name']} ({lang_code}): {result['processed']} pages")

    print("\n" + "=" * 60)
    print("All done!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
