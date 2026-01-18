#!/usr/bin/env python3
"""
HTML Translation Management System
Manages multilingual website translations with manual translation workflow
"""

import os
import json
import sqlite3
import csv
import hashlib
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Set, Tuple, Optional
import re


class HTMLTranslationExtractor(HTMLParser):
    """Extract translatable content from HTML files"""

    # Tags that should not be translated
    SKIP_TAGS = {'script', 'style', 'code', 'pre'}

    # Attributes to translate
    TRANSLATABLE_ATTRS = {
        'title', 'alt', 'placeholder', 'aria-label',
        'aria-description', 'content'
    }

    def __init__(self):
        super().__init__()
        self.translations = []
        self.current_tag_stack = []
        self.skip_content = False

    def handle_starttag(self, tag, attrs):
        self.current_tag_stack.append(tag)

        # Check if we should skip this tag's content
        if tag in self.SKIP_TAGS:
            self.skip_content = True
            return

        # Check for CSS classes to skip
        for attr, value in attrs:
            if attr == 'class' and value:
                # Skip elements with specific classes (e.g., 'no-translate')
                if 'no-translate' in value.split():
                    self.skip_content = True
                    return

        # Extract translatable attributes
        for attr, value in attrs:
            if attr in self.TRANSLATABLE_ATTRS and value and value.strip():
                # Special handling for meta content
                if tag == 'meta' and attr == 'content':
                    # Check if this is a translatable meta tag
                    meta_name = dict(attrs).get('name', '')
                    if meta_name in ['description', 'keywords']:
                        self.translations.append({
                            'type': 'attr',
                            'tag': tag,
                            'attr': attr,
                            'text': value.strip(),
                            'context': f'{tag}[@{attr}]'
                        })
                else:
                    self.translations.append({
                        'type': 'attr',
                        'tag': tag,
                        'attr': attr,
                        'text': value.strip(),
                        'context': f'{tag}[@{attr}]'
                    })

    def handle_endtag(self, tag):
        if self.current_tag_stack and self.current_tag_stack[-1] == tag:
            self.current_tag_stack.pop()

        if tag in self.SKIP_TAGS:
            self.skip_content = False

    def handle_data(self, data):
        if self.skip_content:
            return

        # Skip whitespace-only content
        if not data.strip():
            return

        # Get current context
        context = '/'.join(self.current_tag_stack) if self.current_tag_stack else 'text'

        self.translations.append({
            'type': 'text',
            'tag': self.current_tag_stack[-1] if self.current_tag_stack else None,
            'text': data.strip(),
            'context': context
        })


class TranslationDatabase:
    """Manage translation memory using SQLite"""

    def __init__(self, db_path: str = 'translations.db'):
        self.db_path = db_path
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """Create database tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # Translation memory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_lang, target_lang, source_text, context)
            )
        ''')

        # Path mapping table (for URL consistency)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS path_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_path TEXT NOT NULL,
                target_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_lang, target_lang, source_path)
            )
        ''')

        # File tracking table (for update detection)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                language TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                last_modified TIMESTAMP,
                UNIQUE(file_path, language)
            )
        ''')

        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_translations_lookup
            ON translations(source_lang, target_lang, source_text)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_path_mappings_lookup
            ON path_mappings(source_lang, target_lang, source_path)
        ''')

        self.conn.commit()

    def add_translation(self, source_lang: str, target_lang: str,
                       source_text: str, target_text: str, context: str = None):
        """Add or update a translation"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO translations
            (source_lang, target_lang, source_text, target_text, context, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (source_lang, target_lang, source_text, target_text, context,
              datetime.now()))
        self.conn.commit()

    def get_translation(self, source_lang: str, target_lang: str,
                       source_text: str, context: str = None) -> Optional[str]:
        """Get translation for a text"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT target_text FROM translations
            WHERE source_lang = ? AND target_lang = ?
            AND source_text = ? AND context = ?
        ''', (source_lang, target_lang, source_text, context))

        result = cursor.fetchone()
        return result[0] if result else None

    def add_path_mapping(self, source_lang: str, target_lang: str,
                        source_path: str, target_path: str):
        """Add or update a path mapping"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO path_mappings
            (source_lang, target_lang, source_path, target_path)
            VALUES (?, ?, ?, ?)
        ''', (source_lang, target_lang, source_path, target_path))
        self.conn.commit()

    def get_path_mapping(self, source_lang: str, target_lang: str,
                        source_path: str) -> Optional[str]:
        """Get path mapping"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT target_path FROM path_mappings
            WHERE source_lang = ? AND target_lang = ? AND source_path = ?
        ''', (source_lang, target_lang, source_path))

        result = cursor.fetchone()
        return result[0] if result else None

    def update_file_tracking(self, file_path: str, language: str, content_hash: str):
        """Update file tracking information"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO file_tracking
            (file_path, language, content_hash, last_modified)
            VALUES (?, ?, ?, ?)
        ''', (file_path, language, content_hash, datetime.now()))
        self.conn.commit()

    def get_file_hash(self, file_path: str, language: str) -> Optional[str]:
        """Get stored file hash"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT content_hash FROM file_tracking
            WHERE file_path = ? AND language = ?
        ''', (file_path, language))

        result = cursor.fetchone()
        return result[0] if result else None

    def export_to_json(self, output_path: str):
        """Export all translations to JSON"""
        cursor = self.conn.cursor()

        # Export translations
        cursor.execute('SELECT * FROM translations')
        translations = cursor.fetchall()

        # Export path mappings
        cursor.execute('SELECT * FROM path_mappings')
        path_mappings = cursor.fetchall()

        data = {
            'translations': [
                {
                    'source_lang': row[1],
                    'target_lang': row[2],
                    'source_text': row[3],
                    'target_text': row[4],
                    'context': row[5]
                }
                for row in translations
            ],
            'path_mappings': [
                {
                    'source_lang': row[1],
                    'target_lang': row[2],
                    'source_path': row[3],
                    'target_path': row[4]
                }
                for row in path_mappings
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class TranslationManager:
    """Main translation management system"""

    def __init__(self, source_lang: str = 'en',
                 target_langs: List[str] = None,
                 db_path: str = 'translations.db'):
        self.source_lang = source_lang
        self.target_langs = target_langs or ['fr', 'de', 'pt', 'nl', 'es', 'it', 'ml', 'pa', 'hi']
        self.db = TranslationDatabase(db_path)
        self.base_dir = Path('.')

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def has_file_changed(self, file_path: str) -> bool:
        """Check if file has changed since last processing"""
        current_hash = self.calculate_file_hash(file_path)
        stored_hash = self.db.get_file_hash(file_path, self.source_lang)

        if stored_hash is None:
            return True  # New file

        return current_hash != stored_hash

    def extract_translations(self, html_file: str) -> List[Dict]:
        """Extract translatable content from HTML file"""
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = HTMLTranslationExtractor()
        parser.feed(content)

        return parser.translations

    def extract_from_existing_file(self, source_file: str, target_file: str,
                                   target_lang: str) -> Dict:
        """
        Extract translations from existing translated file

        Args:
            source_file: Source HTML file path
            target_file: Translated HTML file path
            target_lang: Target language code

        Returns:
            Dictionary with extraction results
        """
        # Extract from both files
        source_items = self.extract_translations(source_file)
        target_items = self.extract_translations(target_file)

        # Check if structures match
        if len(source_items) != len(target_items):
            return {
                'success': False,
                'error': 'structure_mismatch',
                'source_count': len(source_items),
                'target_count': len(target_items),
                'translations': []
            }

        # Match by context
        translations = []
        mismatches = []

        for i, source_item in enumerate(source_items):
            target_item = target_items[i]

            # Check if contexts match
            if source_item.get('context') != target_item.get('context'):
                mismatches.append({
                    'index': i,
                    'source_context': source_item.get('context'),
                    'target_context': target_item.get('context')
                })
                continue

            # Create translation pair
            translations.append({
                'source_text': source_item['text'],
                'target_text': target_item['text'],
                'context': source_item.get('context'),
                'type': source_item.get('type', 'text')
            })

        if mismatches:
            return {
                'success': False,
                'error': 'context_mismatch',
                'mismatches': mismatches,
                'translations': translations
            }

        return {
            'success': True,
            'translations': translations,
            'count': len(translations)
        }

    def find_missing_translations(self, source_texts: List[Dict],
                                 target_lang: str) -> List[Dict]:
        """Find texts that don't have translations yet"""
        missing = []

        for item in source_texts:
            text = item['text']
            context = item.get('context')

            translation = self.db.get_translation(
                self.source_lang, target_lang, text, context
            )

            if translation is None:
                missing.append(item)

        return missing

    def export_missing_to_csv(self, missing_translations: List[Dict],
                             target_lang: str, output_file: str):
        """Export missing translations to CSV for manual translation"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_language', 'dest_language', 'source_text',
                           'dest_text', 'context', 'type'])

            for item in missing_translations:
                writer.writerow([
                    self.source_lang,
                    target_lang,
                    item['text'],
                    '',  # Empty for manual translation
                    item.get('context', ''),
                    item.get('type', 'text')
                ])

    def export_extracted_to_csv(self, translations: List[Dict],
                               target_lang: str, output_file: str):
        """Export extracted translations to CSV for review"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_language', 'dest_language', 'source_text',
                           'dest_text', 'context', 'type'])

            for item in translations:
                writer.writerow([
                    self.source_lang,
                    target_lang,
                    item['source_text'],
                    item['target_text'],  # Already translated
                    item.get('context', ''),
                    item.get('type', 'text')
                ])

    def import_translations_from_csv(self, csv_file: str):
        """Import completed translations from CSV"""
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                if row['dest_text'].strip():  # Only import if translation exists
                    self.db.add_translation(
                        row['source_language'],
                        row['dest_language'],
                        row['source_text'],
                        row['dest_text'],
                        row.get('context')
                    )

    def translate_path(self, source_path: str, target_lang: str) -> str:
        """
        Translate file path from source language to target language
        Uses stored mappings for consistency
        """
        # Check if mapping exists
        mapped_path = self.db.get_path_mapping(
            self.source_lang, target_lang, source_path
        )

        if mapped_path:
            return mapped_path

        # If no mapping exists, return a suggested path
        # User should review and confirm path mappings
        parts = Path(source_path).parts

        # Replace language code in path
        new_parts = list(parts)
        if len(new_parts) > 0 and new_parts[0] == self.source_lang:
            new_parts[0] = target_lang

        return str(Path(*new_parts))

    def process_file(self, source_file: str, target_lang: str,
                    check_existing: bool = True) -> Dict:
        """
        Process a single file for translation
        Returns statistics about translation status

        Args:
            source_file: Source file path
            target_lang: Target language code
            check_existing: If True, check for existing translated file
        """
        # Check if file has changed
        if not self.has_file_changed(source_file):
            return {
                'file': source_file,
                'status': 'unchanged',
                'total': 0,
                'found': 0,
                'missing': 0
            }

        # Check for existing translated file
        if check_existing:
            source_normalized = str(Path(source_file)).replace('\\', '/')
            target_path = self.db.get_path_mapping(
                self.source_lang, target_lang, source_normalized
            )

            if target_path and Path(target_path).exists():
                # Existing translated file found
                return {
                    'file': source_file,
                    'status': 'has_existing_translation',
                    'target_file': target_path,
                    'total': 0,
                    'found': 0,
                    'missing': 0
                }

        # Extract translatable content
        translations = self.extract_translations(source_file)

        # Find missing translations
        missing = self.find_missing_translations(translations, target_lang)

        # Update file hash
        file_hash = self.calculate_file_hash(source_file)
        self.db.update_file_tracking(source_file, self.source_lang, file_hash)

        return {
            'file': source_file,
            'status': 'processed',
            'total': len(translations),
            'found': len(translations) - len(missing),
            'missing': len(missing),
            'missing_items': missing
        }

    def generate_translation_overview(self, output_file: str = 'translation_overview.html'):
        """Generate HTML overview of all translations"""
        # Collect all files
        source_files = list(Path(self.source_lang).rglob('*.html'))

        # Process statistics for each language
        stats_by_lang = {}

        for lang in self.target_langs:
            stats_by_lang[lang] = []

            for source_file in source_files:
                result = self.process_file(str(source_file), lang)
                stats_by_lang[lang].append(result)

        # Generate HTML
        html = self._generate_overview_html(source_files, stats_by_lang)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

    def _generate_overview_html(self, source_files: List[Path],
                               stats_by_lang: Dict) -> str:
        """Generate HTML content for translation overview"""
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Overview</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .complete {
            background-color: #4CAF50;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
        }
        .partial {
            background-color: #FF9800;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
        }
        .missing {
            background-color: #F44336;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
        }
        .stats {
            margin-top: 20px;
            padding: 15px;
            background-color: white;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>Translation Overview</h1>
    <p>Generated: ''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '''</p>

    <table>
        <thead>
            <tr>
                <th>File</th>
'''

        # Add language columns
        for lang in self.target_langs:
            html += f'                <th>{lang.upper()}</th>\n'

        html += '''            </tr>
        </thead>
        <tbody>
'''

        # Add rows for each file
        for idx, source_file in enumerate(source_files):
            html += f'            <tr>\n'
            html += f'                <td>{source_file}</td>\n'

            for lang in self.target_langs:
                stats = stats_by_lang[lang][idx]

                if stats['total'] == 0:
                    status_html = '<span class="missing">-</span>'
                elif stats['missing'] == 0:
                    status_html = f'<span class="complete">100%</span>'
                else:
                    percentage = int((stats['found'] / stats['total']) * 100)
                    if percentage > 0:
                        status_html = f'<span class="partial">{percentage}%</span>'
                    else:
                        status_html = f'<span class="missing">0%</span>'

                html += f'                <td>{status_html}</td>\n'

            html += '            </tr>\n'

        html += '''        </tbody>
    </table>

    <div class="stats">
        <h2>Summary Statistics</h2>
'''

        # Add summary statistics
        for lang in self.target_langs:
            total_texts = sum(s['total'] for s in stats_by_lang[lang])
            total_found = sum(s['found'] for s in stats_by_lang[lang])
            total_missing = sum(s['missing'] for s in stats_by_lang[lang])

            if total_texts > 0:
                percentage = int((total_found / total_texts) * 100)
            else:
                percentage = 0

            html += f'''        <p><strong>{lang.upper()}:</strong>
                {total_found}/{total_texts} translated ({percentage}%) -
                {total_missing} missing</p>\n'''

        html += '''    </div>
</body>
</html>
'''

        return html

    def create_path_mapping_template(self, output_file: str = 'path_mappings.csv'):
        """Create a template CSV for path mappings"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_lang', 'target_lang', 'source_path', 'target_path'])

            # Example mappings
            writer.writerow(['en', 'fr', 'en/travel', 'fr/voyages'])
            writer.writerow(['en', 'fr', 'en/photography', 'fr/photographie'])

    def import_path_mappings(self, csv_file: str):
        """Import path mappings from CSV"""
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                if row['target_path'].strip():
                    self.db.add_path_mapping(
                        row['source_lang'],
                        row['target_lang'],
                        row['source_path'],
                        row['target_path']
                    )

    def get_files_from_mappings(self, target_lang: str) -> list:
        """
        Get list of source files based on path mappings in DB

        Args:
            target_lang: Target language code

        Returns:
            List of source file paths to process
        """
        cursor = self.db.conn.cursor()

        # Get all path mappings for this target language
        cursor.execute('''
            SELECT DISTINCT source_path FROM path_mappings
            WHERE source_lang = ? AND target_lang = ?
        ''', (self.source_lang, target_lang))

        mappings = cursor.fetchall()
        files_to_process = set()  # Use set to avoid duplicates

        for (source_path,) in mappings:
            # DB stores paths with forward slashes, but OS uses backslashes on Windows
            # Convert to OS-specific path
            path_obj = Path(source_path)

            # Check if path exists
            if not path_obj.exists():
                print(f"Warning: Mapped path does not exist: {source_path}")
                continue

            # Check if it's a file
            if path_obj.is_file():
                # Store with forward slashes for consistency
                files_to_process.add(source_path)
            # Check if it's a directory
            elif path_obj.is_dir():
                # Get only direct children (*.html, not **/*.html)
                for html_file in path_obj.glob('*.html'):
                    if html_file.is_file():
                        # Convert back to forward slashes for consistency
                        normalized_path = str(html_file).replace('\\', '/')
                        files_to_process.add(normalized_path)

        return sorted(list(files_to_process))

    def extract_for_language(self, target_lang: str, output_dir: str = 'translations_pending') -> dict:
        """
        Extract missing translations for a specific language
        Only processes files with path mappings

        Args:
            target_lang: Target language code
            output_dir: Directory for output CSV files

        Returns:
            Dictionary with statistics
        """
        # Get files based on mappings
        files_to_process = self.get_files_from_mappings(target_lang)

        if not files_to_process:
            return {
                'total_files': 0,
                'processed': 0,
                'missing_count': 0,
                'message': f'No path mappings found for {target_lang}'
            }

        total_missing = 0
        processed_files = 0
        extracted_from_existing = 0

        for source_file in files_to_process:
            if not Path(source_file).exists():
                print(f"Warning: Mapped file not found: {source_file}")
                continue

            result = self.process_file(source_file, target_lang, check_existing=True)

            # Handle existing translated file
            if result['status'] == 'has_existing_translation':
                target_file = result['target_file']
                print(f"  {source_file}: Found existing translation at {target_file}")

                # Extract translations from existing file
                extract_result = self.extract_from_existing_file(
                    source_file, target_file, target_lang
                )

                if extract_result['success']:
                    # Export to CSV for review
                    output_csv = Path(output_dir) / f"extracted_{target_lang}_{Path(source_file).stem}.csv"
                    self.export_extracted_to_csv(
                        extract_result['translations'],
                        target_lang,
                        str(output_csv)
                    )
                    print(f"    Extracted {extract_result['count']} translations -> {output_csv}")
                    extracted_from_existing += 1
                else:
                    # Structure mismatch
                    if extract_result['error'] == 'structure_mismatch':
                        print(f"    WARNING:  Warning: HTML structure mismatch")
                        print(f"       Source has {extract_result['source_count']} elements, "
                              f"target has {extract_result['target_count']} elements")
                        print(f"       Skipping this file - manual review needed")
                    elif extract_result['error'] == 'context_mismatch':
                        print(f"    WARNING:  Warning: Context mismatch in {len(extract_result['mismatches'])} elements")
                        for mm in extract_result['mismatches'][:3]:  # Show first 3
                            print(f"       Element {mm['index']}: {mm['source_context']} != {mm['target_context']}")
                        print(f"       Skipping this file - manual review needed")

                processed_files += 1
                continue

            # No existing file - process normally
            if result['missing'] > 0:
                # Export missing translations to CSV
                output_csv = Path(output_dir) / f"missing_{target_lang}_{Path(source_file).stem}.csv"
                self.export_missing_to_csv(
                    result['missing_items'],
                    target_lang,
                    str(output_csv)
                )
                total_missing += result['missing']
                print(f"  {source_file}: {result['missing']} missing -> {output_csv}")
            else:
                print(f"  {source_file}: fully translated")

            processed_files += 1

        return {
            'total_files': len(files_to_process),
            'processed': processed_files,
            'missing_count': total_missing,
            'extracted_from_existing': extracted_from_existing
        }

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='HTML Translation Management System'
    )

    parser.add_argument('command', choices=[
        'extract', 'import', 'overview', 'export',
        'path-template', 'import-paths'
    ])

    parser.add_argument('--source-lang', default='en',
                       help='Source language code (default: en)')

    parser.add_argument('--target-lang',
                       help='Target language code (for extract command)')

    parser.add_argument('--file',
                       help='HTML file to process')

    parser.add_argument('--csv',
                       help='CSV file for import/export')

    parser.add_argument('--output',
                       help='Output file')

    args = parser.parse_args()

    # Initialize manager
    manager = TranslationManager(source_lang=args.source_lang)

    try:
        if args.command == 'extract':
            if not args.file or not args.target_lang:
                print("Error: --file and --target-lang required for extract")
                return

            result = manager.process_file(args.file, args.target_lang)

            print(f"File: {result['file']}")
            print(f"Total texts: {result['total']}")
            print(f"Found translations: {result['found']}")
            print(f"Missing translations: {result['missing']}")

            if result['missing'] > 0:
                output_csv = args.output or f"missing_{args.target_lang}.csv"
                manager.export_missing_to_csv(
                    result['missing_items'],
                    args.target_lang,
                    output_csv
                )
                print(f"\nMissing translations exported to: {output_csv}")

        elif args.command == 'import':
            if not args.csv:
                print("Error: --csv required for import")
                return

            manager.import_translations_from_csv(args.csv)
            print(f"Translations imported from: {args.csv}")

        elif args.command == 'overview':
            output_html = args.output or 'translation_overview.html'
            manager.generate_translation_overview(output_html)
            print(f"Translation overview generated: {output_html}")

        elif args.command == 'export':
            output_json = args.output or 'translations_export.json'
            manager.db.export_to_json(output_json)
            print(f"Translations exported to: {output_json}")

        elif args.command == 'path-template':
            output_csv = args.output or 'path_mappings.csv'
            manager.create_path_mapping_template(output_csv)
            print(f"Path mapping template created: {output_csv}")

        elif args.command == 'import-paths':
            if not args.csv:
                print("Error: --csv required for import-paths")
                return

            manager.import_path_mappings(args.csv)
            print(f"Path mappings imported from: {args.csv}")

    finally:
        manager.close()


if __name__ == '__main__':
    main()
