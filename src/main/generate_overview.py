#!/usr/bin/env python3
"""
Generate translation overview based on path mappings only
"""

from pathlib import Path
from datetime import datetime
from translate_manager import TranslationManager
from html.parser import HTMLParser


# Get repository root (two levels up from this script)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TitleExtractor(HTMLParser):
    """Extract title from HTML file"""
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and self.title is None:
            self.title = data.strip()


def extract_title(html_file):
    """Extract title from HTML file"""
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = TitleExtractor()
        parser.feed(content)
        return parser.title or Path(html_file).stem
    except Exception:
        return Path(html_file).stem


# Language code to native name mapping
LANGUAGE_NAMES = {
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch',
    'pt': 'Português',
    'nl': 'Nederlands',
    'es': 'Español',
    'it': 'Italiano',
    'ml': 'മലയാളം',
    'pa': 'ਪੰਜਾਬੀ',
    'hi': 'हिन्दी'
}


def generate_overview(output_file='analysis/translation_overview.html'):
    """Generate HTML overview showing only mapped files"""

    # Use absolute path for database
    db_path = REPO_ROOT / 'translations.db'
    manager = TranslationManager(db_path=str(db_path))

    try:
        # Get all unique source files from mappings across all languages
        cursor = manager.db.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT source_path FROM path_mappings
            WHERE source_lang = ?
        ''', (manager.source_lang,))

        all_mapped_files = set()
        for (source_path,) in cursor.fetchall():
            path_obj = REPO_ROOT / source_path
            if path_obj.is_file():
                all_mapped_files.add(source_path)
            elif path_obj.is_dir():
                # Get direct children
                for html_file in path_obj.glob('*.html'):
                    if html_file.is_file():
                        # Store relative path from repo root
                        rel_path = html_file.relative_to(REPO_ROOT)
                        all_mapped_files.add(str(rel_path).replace('\\', '/'))

        source_files = sorted(list(all_mapped_files))

        if not source_files:
            print("No mapped files found. Add mappings to path_mappings.csv and run import-paths.")
            return

        # Extract titles for each file
        file_titles = {}
        for source_file in source_files:
            full_path = REPO_ROOT / source_file
            if full_path.exists():
                file_titles[source_file] = extract_title(str(full_path))
            else:
                file_titles[source_file] = Path(source_file).stem

        # Process statistics for each language and get target paths
        from translate_manager import HTMLTranslationExtractor

        stats_by_lang = {}
        target_paths_by_lang = {}

        for lang in manager.target_langs:
            stats_by_lang[lang] = []
            target_paths_by_lang[lang] = []

            for source_file in source_files:
                full_source_path = REPO_ROOT / source_file
                if not full_source_path.exists():
                    stats_by_lang[lang].append({
                        'file': source_file,
                        'total': 0,
                        'found': 0,
                        'missing': 0
                    })
                    target_paths_by_lang[lang].append(None)
                    continue

                # Extract translatable items from source file
                extractor = HTMLTranslationExtractor()
                with open(full_source_path, 'r', encoding='utf-8') as f:
                    extractor.feed(f.read())

                total = len(extractor.translations)
                found = 0

                # Check how many have translations in database
                cursor = manager.db.conn.cursor()
                for item in extractor.translations:
                    cursor.execute('''
                        SELECT COUNT(*) FROM translations
                        WHERE source_lang = ? AND target_lang = ?
                        AND source_text = ?
                    ''', (manager.source_lang, lang, item['text']))

                    if cursor.fetchone()[0] > 0:
                        found += 1

                stats_by_lang[lang].append({
                    'file': source_file,
                    'total': total,
                    'found': found,
                    'missing': total - found
                })

                # Get target path for linking
                source_path_normalized = str(Path(source_file)).replace('\\', '/')
                target_path = manager.db.get_path_mapping(
                    manager.source_lang, lang, source_path_normalized
                )
                if not target_path:
                    # Try directory mapping
                    source_dir = str(Path(source_file).parent).replace('\\', '/')
                    target_dir = manager.db.get_path_mapping(
                        manager.source_lang, lang, source_dir
                    )
                    if target_dir:
                        target_path = str(Path(target_dir) / Path(source_file).name).replace('\\', '/')

                target_paths_by_lang[lang].append(target_path)

        # Generate HTML
        html = _generate_overview_html(source_files, file_titles, stats_by_lang,
                                       target_paths_by_lang, manager.target_langs)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"Overview generated: {output_file}")
        print(f"  Showing {len(source_files)} mapped files")

    finally:
        manager.close()


def _generate_overview_html(source_files, file_titles, stats_by_lang,
                            target_paths_by_lang, target_langs):
    """Generate HTML content for translation overview"""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Overview</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --color-base-bg: #fafbfc;
            --color-base-surface: #ffffff;
            --color-base-text: #1a202c;
            --color-base-text-muted: #4a5568;
            --color-accent-1: #87634B;
            --color-accent-2: #6B4E3D;
            --color-accent-3: #A07856;
            --color-accent-light: #F5F0EB;
            --color-shadow: rgba(135, 99, 75, 0.15);
            --color-border: rgba(135, 99, 75, 0.12);
            --color-hover: rgba(135, 99, 75, 0.08);
            --space-xs: 0.25rem;
            --space-sm: 0.5rem;
            --space-md: 1rem;
            --space-lg: 1.5rem;
            --space-xl: 2rem;
            --space-2xl: 3rem;
            --space-3xl: 4rem;
            --radius-sm: 6px;
            --radius-md: 12px;
            --radius-lg: 18px;
            --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06);
            --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.06), 0 2px 4px rgba(0, 0, 0, 0.04);
            --shadow-lg: 0 10px 24px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.06);
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;

            --color-complete: #48bb78;
            --color-partial: #ed8936;
            --color-missing: #f56565;
        }

        html {
            scroll-behavior: smooth;
        }

        body {
            font-family: var(--font-sans);
            font-size: 16px;
            line-height: 1.6;
            color: var(--color-base-text);
            background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);
            min-height: 100vh;
            padding: var(--space-2xl);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            margin-bottom: var(--space-3xl);
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--color-accent-2);
            margin-bottom: var(--space-md);
            letter-spacing: -0.02em;
        }

        .info {
            background: linear-gradient(135deg, var(--color-accent-light) 0%, rgba(135, 99, 75, 0.05) 100%);
            padding: var(--space-lg);
            border-left: 4px solid var(--color-accent-1);
            margin-bottom: var(--space-2xl);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
        }

        .info strong {
            color: var(--color-accent-2);
        }

        .table-container {
            background: var(--color-base-surface);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow-md);
            margin-bottom: var(--space-2xl);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: var(--space-lg);
            text-align: left;
            border-bottom: 1px solid var(--color-border);
        }

        th {
            background: linear-gradient(135deg, var(--color-accent-2) 0%, var(--color-accent-1) 100%);
            color: white;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
            text-transform: capitalize;
            font-size: 0.95rem;
            letter-spacing: 0.02em;
        }

        tbody tr {
            transition: all 0.2s ease;
        }

        tbody tr:hover {
            background-color: var(--color-hover);
        }

        tbody tr:last-child td {
            border-bottom: none;
        }

        .file-cell {
            font-weight: 500;
        }

        .file-cell a {
            color: var(--color-accent-2);
            text-decoration: none;
            transition: color 0.2s ease;
            display: block;
        }

        .file-cell a:hover {
            color: var(--color-accent-1);
            text-decoration: underline;
        }

        .status-badge {
            display: inline-block;
            padding: var(--space-xs) var(--space-md);
            border-radius: var(--radius-sm);
            font-weight: 600;
            font-size: 0.875rem;
            min-width: 60px;
            text-align: center;
            text-decoration: none;
            transition: all 0.2s ease;
        }

        .status-badge:hover {
            transform: translateY(-1px);
            box-shadow: var(--shadow-sm);
        }

        .complete {
            background-color: var(--color-complete);
            color: white;
        }

        .partial {
            background-color: var(--color-partial);
            color: white;
        }

        .missing {
            background-color: var(--color-missing);
            color: white;
        }

        .stats {
            background: var(--color-base-surface);
            padding: var(--space-xl);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-md);
        }

        .stats h2 {
            font-size: 1.5rem;
            color: var(--color-accent-2);
            margin-bottom: var(--space-lg);
            font-weight: 600;
        }

        .lang-stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: var(--space-md);
        }

        .lang-stat {
            padding: var(--space-lg);
            background: linear-gradient(135deg, var(--color-base-bg) 0%, #ffffff 100%);
            border-left: 4px solid var(--color-accent-1);
            border-radius: var(--radius-md);
            transition: all 0.2s ease;
        }

        .lang-stat:hover {
            transform: translateX(4px);
            box-shadow: var(--shadow-sm);
        }

        .lang-name {
            font-weight: 700;
            font-size: 1.1rem;
            color: var(--color-accent-2);
            margin-bottom: var(--space-sm);
        }

        .lang-progress {
            color: var(--color-base-text-muted);
            font-size: 0.95rem;
        }

        .progress-bar {
            margin-top: var(--space-sm);
            height: 8px;
            background-color: var(--color-base-bg);
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
            border-radius: 4px;
        }

        @media (max-width: 768px) {
            body {
                padding: var(--space-md);
            }

            h1 {
                font-size: 2rem;
            }

            table {
                font-size: 0.9rem;
            }

            th, td {
                padding: var(--space-md);
            }

            .lang-stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Translation Overview</h1>
        </header>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>English</th>
'''

    # Add language columns with full names
    for lang in target_langs:
        lang_name = LANGUAGE_NAMES.get(lang, lang.upper())
        html += f'                        <th>{lang_name}</th>\n'

    html += '''                    </tr>
                </thead>
                <tbody>
'''

    # Add rows for each file
    for idx, source_file in enumerate(source_files):
        html += '                    <tr>\n'

        # File cell with title and link - use relative path from root with ./
        title = file_titles.get(source_file, Path(source_file).stem)
        relative_path = './' + source_file.replace('\\', '/')
        html += f'                        <td class="file-cell"><a href="{relative_path}" title="{source_file}">{title}</a></td>\n'

        for lang in target_langs:
            stats = stats_by_lang[lang][idx]
            target_path = target_paths_by_lang[lang][idx]

            if stats['total'] == 0:
                status_html = '<span class="status-badge missing">-</span>'
            elif stats['missing'] == 0:
                # Complete - check if file exists to provide link
                target_exists = target_path and (REPO_ROOT / target_path).exists()
                if target_exists:
                    relative_target = './' + target_path.replace('\\', '/')
                    status_html = f'<a href="{relative_target}" class="status-badge complete">100%</a>'
                else:
                    # Link to English version if translation doesn't exist
                    status_html = f'<a href="{relative_path}" class="status-badge complete">100%</a>'
            else:
                percentage = int((stats['found'] / stats['total']) * 100)
                # Partial - check if file exists to provide link
                if percentage > 0:
                    target_exists = target_path and (REPO_ROOT / target_path).exists()
                    if target_exists:
                        relative_target = './' + target_path.replace('\\', '/')
                        status_html = f'<a href="{relative_target}" class="status-badge partial">{percentage}%</a>'
                    else:
                        # Link to English version if translation doesn't exist
                        status_html = f'<a href="{relative_path}" class="status-badge partial">{percentage}%</a>'
                else:
                    # Link to English version for missing translations
                    status_html = f'<a href="{relative_path}" class="status-badge missing">0%</a>'

            html += f'                        <td>{status_html}</td>\n'

        html += '                    </tr>\n'

    html += '''                </tbody>
            </table>
        </div>

        <div class="stats">
            <h2>Summary Statistics</h2>
            <div class="lang-stats-grid">
'''

    # Add summary statistics with improved styling
    for lang in target_langs:
        total_texts = sum(s['total'] for s in stats_by_lang[lang])
        total_found = sum(s['found'] for s in stats_by_lang[lang])
        total_missing = sum(s['missing'] for s in stats_by_lang[lang])

        if total_texts > 0:
            percentage = int((total_found / total_texts) * 100)
        else:
            percentage = 0

        # Color based on completion
        if percentage == 100:
            color = 'var(--color-complete)'
        elif percentage > 0:
            color = 'var(--color-partial)'
        else:
            color = 'var(--color-missing)'

        lang_name = LANGUAGE_NAMES.get(lang, lang.upper())

        html += f'''                <div class="lang-stat" style="border-left-color: {color}">
                    <div class="lang-name">{lang_name}</div>
                    <div class="lang-progress">
                        {total_found}/{total_texts} translated ({percentage}%) · {total_missing} missing
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {percentage}%; background-color: {color};"></div>
                    </div>
                </div>
'''

    html += '''            </div>
        </div>

        <div class="info">
            <strong>Note:</strong> This overview shows only files with path mappings in the database.
            <br><strong>Generated:</strong> ''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '''
        </div>
    </div>
</body>
</html>
'''

    return html


if __name__ == '__main__':
    generate_overview()
