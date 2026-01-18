#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Language Search Index Generator
Generates search indexes for all language directories (en, fr, ml, pa, hi)
"""

import os
import sys
import json
import re
from pathlib import Path
from html.parser import HTMLParser

# Set UTF-8 encoding for output (fixes Windows console issues)
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')

# Configuration
SCRIPT_DIR = Path(__file__).parent if '__file__' in globals() else Path.cwd()
SCRIPT_DIR = Path.cwd()

# Language directories to process
LANGUAGES = {
    'en': 'English',
    'fr': 'Français',
    'ml': 'മലയാളം',
    'pa': 'ਪੰਜਾਬੀ',
    'hi': 'हिन्दी',
}

# Categories based on directory structure
CATEGORY_MAP = {
    'research': 'research',
    'teaching': 'teaching',
    'writings': 'writings',
    'linguistics': 'linguistics',
    'photography': 'photography',
    'travel': 'travel',
    'blog': 'blog',
    'projects': 'projects',
    'programming': 'programming',
}

# Files/directories to exclude
# Note: These patterns match against the relative path from BASE_DIR
EXCLUDE_PATTERNS = [
    r'node_modules',        # node_modules directory
    r'search-index\.json$', # search index file
    r'search\.html$',       # search page itself
]


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML"""

    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {'script', 'style', 'nav', 'footer'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)


def get_all_html_files(directory):
    """Get all HTML files recursively"""
    html_files = []

    # Use Path.rglob to find all HTML files
    all_files = list(directory.rglob('*.html'))

    for file_path in all_files:
        # Check against relative path from base directory
        relative_path = str(file_path.relative_to(directory))

        # Check if file should be excluded
        excluded = any(re.search(pattern, relative_path) for pattern in EXCLUDE_PATTERNS)
        if not excluded:
            html_files.append(file_path)

    return html_files


def get_category(file_path, base_dir):
    """Determine category from file path"""
    relative_path = file_path.relative_to(base_dir)
    parts = relative_path.parts

    for key, value in CATEGORY_MAP.items():
        if parts[0] == key or key in str(relative_path):
            return value

    return 'general'


def extract_title(html, file_path):
    """Extract title from HTML"""
    # Try <title> tag
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        if title:
            return re.sub(r'<[^>]+>', '', title)  # Remove any HTML tags

    # Try <h1> tag
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if h1_match:
        h1 = h1_match.group(1).strip()
        if h1:
            return re.sub(r'<[^>]+>', '', h1)

    # Fallback to filename
    return file_path.stem.replace('-', ' ').title()


def extract_description(html):
    """Extract meta description or first paragraph"""
    # Try meta description
    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if desc_match:
        return desc_match.group(1).strip()

    # Try first paragraph
    p_match = re.search(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
    if p_match:
        text = re.sub(r'<[^>]+>', '', p_match.group(1))
        return text.strip()[:200]

    return ''


def extract_content(html):
    """Extract text content from HTML"""
    try:
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text
    except Exception as e:
        print(f"Error extracting content: {e}")
        return ''


def process_file(file_path, base_dir):
    """Process a single HTML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()

        relative_path = file_path.relative_to(base_dir)
        url = './' + str(relative_path).replace('\\', '/')

        title = extract_title(html, file_path)
        content = extract_content(html)
        description = extract_description(html)
        category = get_category(file_path, base_dir)

        return {
            'url': url,
            'title': title,
            'description': description,
            'content': content[:1000],  # Limit content length
            'category': category,
            'path': str(relative_path),
        }
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def build_search_index_for_language(lang_code, lang_name):
    """Build search index for a specific language"""
    base_dir = SCRIPT_DIR / lang_code
    output_file = base_dir / 'search-index.json'

    print(f"\n{'='*60}")
    print(f"Building search index for {lang_name} ({lang_code})")
    print(f"{'='*60}")
    print(f"Base directory: {base_dir}")

    # Check if directory exists
    if not base_dir.exists():
        print(f"[WARNING] Directory {base_dir} does not exist. Skipping.")
        return None

    if not base_dir.is_dir():
        print(f"[WARNING] {base_dir} is not a directory. Skipping.")
        return None

    # Get all HTML files
    html_files = get_all_html_files(base_dir)
    print(f"Found {len(html_files)} HTML files")

    if len(html_files) == 0:
        print(f"[WARNING] No HTML files found. Skipping.")
        return None

    # Process each file
    index = []
    processed = 0

    for i, file_path in enumerate(html_files):
        entry = process_file(file_path, base_dir)
        if entry:
            index.append(entry)
            processed += 1

        # Progress indicator
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(html_files)} files...")

    print(f"Successfully processed {processed} files")

    # Write index to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"[OK] Search index written to: {output_file}")

    # Print statistics
    categories = {}
    for item in index:
        category = item['category']
        categories[category] = categories.get(category, 0) + 1

    print("\nCategory breakdown:")
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")

    # Get file size
    file_size = output_file.stat().st_size
    if file_size < 1024:
        size_str = f"{file_size} B"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size / (1024 * 1024):.1f} MB"

    print(f"\nIndex file size: {size_str}")

    return {
        'lang_code': lang_code,
        'lang_name': lang_name,
        'total_files': len(html_files),
        'processed': processed,
        'output_file': str(output_file),
        'file_size': file_size,
        'categories': categories,
    }


def main():
    """Main function to build search indexes for all languages"""
    print("="*60)
    print("Multi-Language Search Index Generator")
    print("="*60)
    print(f"Working directory: {SCRIPT_DIR}")
    print(f"Languages to process: {', '.join(LANGUAGES.keys())}")

    results = {}

    for lang_code, lang_name in LANGUAGES.items():
        result = build_search_index_for_language(lang_code, lang_name)
        if result:
            results[lang_code] = result

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if not results:
        print("No search indexes were generated.")
        return

    total_files = sum(r['processed'] for r in results.values())
    total_size = sum(r['file_size'] for r in results.values())

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

    print("\n" + "="*60)
    print("All done!")
    print("="*60)


if __name__ == '__main__':
    main()
