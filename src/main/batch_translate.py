#!/usr/bin/env python3
"""
Batch Translation Helper Script
Automates the extraction and import workflow for multiple files
"""

import os
import sys
import glob
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from translate_manager import TranslationManager

from html_generator import HTMLGenerator


# Get repository root (two levels up from this script)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Configuration
SOURCE_LANG = "en"
TARGET_LANGS = ["fr", "de", "pt", "nl", "es", "it", "ml", "pa", "hi"]
SOURCE_DIR = "en/photography"
OUTPUT_DIR = "translations_pending"


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

    @staticmethod
    def supports_color():
        """Check if terminal supports colors"""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    @classmethod
    def disable_if_needed(cls):
        """Disable colors if terminal doesn't support them"""
        if not cls.supports_color():
            cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.NC = ''


# Disable colors on Windows or if not supported
Colors.disable_if_needed()


def print_info(message):
    """Print info message in green"""
    print(f"{Colors.GREEN}[INFO]{Colors.NC} {message}")


def print_warning(message):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")


def print_error(message):
    """Print error message in red"""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def extract_for_file(manager, file_path, lang):
    """
    Extract translations for a single file and language

    Returns:
        bool: True if there are missing translations, False otherwise
    """
    basename = Path(file_path).stem
    output_csv = Path(OUTPUT_DIR) / f"missing_{lang}_{basename}.csv"

    print_info(f"Extracting {basename} for {lang}...")

    result = manager.process_file(str(file_path), lang)

    if result['missing'] == 0:
        print_info(f"  ✓ No missing translations for {lang}")
        return False
    else:
        manager.export_missing_to_csv(
            result['missing_items'],
            lang,
            str(output_csv)
        )
        print_warning(f"  → {result['missing']} translations needed (saved to {output_csv})")
        return True


def process_file(manager, file_path):
    """
    Process a single HTML file for all target languages

    Returns:
        bool: True if any language has missing translations
    """
    print_info(f"Processing: {file_path}")

    has_missing = False

    for lang in TARGET_LANGS:
        if extract_for_file(manager, file_path, lang):
            has_missing = True

    if not has_missing:
        print_info(f"✓ File fully translated: {file_path}")

    print()  # Empty line for readability
    return has_missing


def extract_all(source_dir=SOURCE_DIR):
    """Extract translations based on path mappings in DB"""
    print_info("Starting extraction based on path mappings")
    print_info(f"Target languages: {', '.join(TARGET_LANGS)}")
    print()

    # Create output directory
    output_dir = REPO_ROOT / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize manager V2 (mapping-based)
    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / "translations.db"))

    try:
        total_missing = 0

        for lang in TARGET_LANGS:
            print_info(f"Processing {lang}...")
            stats = manager.extract_for_language(lang, str(output_dir))

            if stats['total_files'] == 0:
                print_warning(f"  No path mappings for {lang}")
            else:
                print_info(f"  {stats['processed']} files, {stats['missing_count']} missing translations")
                total_missing += stats['missing_count']

            print()

        # Show statistics
        show_statistics()

        if total_missing > 0:
            print_info(f"Done! Edit CSV files in {OUTPUT_DIR} and run: python {sys.argv[0]} import")
        else:
            print_info("All mapped files are fully translated!")

    finally:
        manager.close()

    return 0


def extract_file(file_path):
    """Extract translations for a single file"""
    # Check if file exists
    full_path = REPO_ROOT / file_path
    if not full_path.is_file():
        print_error(f"File not found: {file_path}")
        return 1

    # Create output directory
    output_dir = REPO_ROOT / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize manager
    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / "translations.db"))

    try:
        process_file(manager, file_path)
        show_statistics()
    finally:
        manager.close()

    return 0


def import_translations():
    """Import completed translations from CSV files"""
    print_info("Importing completed translations...")

    # Initialize manager
    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / "translations.db"))

    try:
        # Find all CSV files in output directory
        output_dir = REPO_ROOT / OUTPUT_DIR
        csv_files = list(output_dir.glob('*.csv'))

        if not csv_files:
            print_warning(f"No CSV files found in {OUTPUT_DIR}")
            return 0

        imported = 0
        total = len(csv_files)

        # Create completed directory
        completed_dir = output_dir / 'completed'
        completed_dir.mkdir(parents=True, exist_ok=True)

        for csv_file in csv_files:
            # Check if CSV has translations
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Check if any line has content in dest_text column (column 3)
            has_translations = False
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 4 and parts[3].strip():
                        has_translations = True
                        break

            if has_translations:
                print_info(f"Importing: {csv_file.name}")
                manager.import_translations_from_csv(str(csv_file))
                imported += 1

                # Move to completed folder
                shutil.move(str(csv_file), str(completed_dir / csv_file.name))
            else:
                print_warning(f"Skipping (not completed): {csv_file.name}")

        print_info(f"Imported {imported}/{total} CSV files")

        # Generate overview
        generate_overview(manager)

        # Show statistics
        show_statistics()

    finally:
        manager.close()

    return 0


def generate_overview(manager=None):
    """Generate translation overview HTML (mapping-based)"""
    print_info("Generating translation overview...")

    # Use the new mapping-based overview generator
    from generate_overview import generate_overview as gen_overview

    output_path = REPO_ROOT / 'translation_overview.html'
    gen_overview(str(output_path))
    print_info(f"Overview saved to: translation_overview.html")


def show_statistics():
    """Show translation statistics"""
    print_info("Translation Statistics:")

    # Count pending CSVs
    pending_dir = REPO_ROOT / OUTPUT_DIR
    pending_csvs = list(pending_dir.glob('*.csv'))
    pending = len(pending_csvs)

    # Count completed CSVs
    completed_dir = pending_dir / 'completed'
    completed = 0
    if completed_dir.is_dir():
        completed_csvs = list(completed_dir.glob('*.csv'))
        completed = len(completed_csvs)

    print(f"  Pending translations: {pending} CSV files")
    print(f"  Completed imports: {completed} CSV files")

    # Show database statistics if it exists
    db_path = REPO_ROOT / 'translations.db'
    if db_path.is_file():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM translations")
        trans_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM path_mappings")
        path_count = cursor.fetchone()[0]

        print(f"  Database: {trans_count} translations, {path_count} path mappings")

        conn.close()


def setup():
    """Initial setup - create path mapping template"""
    print_info("Setting up translation system...")

    path_mappings_file = REPO_ROOT / 'path_mappings.csv'

    if path_mappings_file.exists():
        print_warning("path_mappings.csv already exists")
        return 0

    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / 'translations.db'))

    try:
        manager.create_path_mapping_template(str(path_mappings_file))
        print_info(f"Created {path_mappings_file}")
        print_info(f"Please edit {path_mappings_file} and run: python {sys.argv[0]} import-paths")
    finally:
        manager.close()

    return 0


def import_paths():
    """Import path mappings from CSV"""
    path_mappings_file = REPO_ROOT / 'path_mappings.csv'

    if not path_mappings_file.exists():
        print_error(f"{path_mappings_file} not found")
        print_info(f"Run: python {sys.argv[0]} setup")
        return 1

    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / "translations.db"))

    try:
        manager.import_path_mappings(str(path_mappings_file))
        print_info("Path mappings imported")
    finally:
        manager.close()

    return 0


def export_database():
    """Export database to JSON"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"translations_backup_{timestamp}.json"

    manager = TranslationManager(source_lang=SOURCE_LANG, target_langs=TARGET_LANGS, db_path=str(REPO_ROOT / "translations.db"))

    try:
        manager.db.export_to_json(output_file)
        print_info(f"Database exported to: {output_file}")
    finally:
        manager.close()

    return 0


def generate_html_file(source_file, target_lang):
    """Generate translated HTML file"""
    if len(sys.argv) < 3:
        print_error("Usage: python {} generate-file <source_file> <target_lang>".format(sys.argv[0]))
        return 1

    if not Path(source_file).exists():
        print_error(f"File not found: {source_file}")
        return 1

    print_info(f"Generating {target_lang} version of {source_file}...")

    generator = HTMLGenerator(source_lang=SOURCE_LANG)

    try:
        output_file = generator.translate_file(source_file, target_lang)
        print_info(f"✓ Generated: {output_file}")
    finally:
        generator.close()

    return 0


def generate_html_all(target_lang=None):
    """
    Generate/regenerate HTML files based on mappings
    - NEW files: only if explicit mapping exists
    - EXISTING files: regenerate if translations updated (check file mtime)
    """
    langs_to_generate = [target_lang] if target_lang else TARGET_LANGS

    manager = TranslationManager(source_lang=SOURCE_LANG, db_path=str(REPO_ROOT / "translations.db"))

    try:
        for lang in langs_to_generate:
            print_info(f"Generating HTML files for {lang}...")

            # Get all files with mappings
            files_to_process = manager.get_files_from_mappings(lang)

            if not files_to_process:
                print_warning(f"  No path mappings for {lang}")
                continue

            generator = HTMLGenerator(source_lang=SOURCE_LANG)
            generated_count = 0
            skipped_count = 0
            regenerated_count = 0

            try:
                for source_file in files_to_process:
                    if not Path(source_file).exists():
                        print_warning(f"  Source file not found: {source_file}")
                        continue

                    try:
                        # Determine output file path
                        source_path_normalized = str(Path(source_file)).replace('\\', '/')

                        # Try exact file mapping
                        target_path = manager.db.get_path_mapping(
                            SOURCE_LANG, lang, source_path_normalized
                        )

                        if not target_path:
                            # Try directory mapping
                            source_dir = str(Path(source_file).parent).replace('\\', '/')
                            target_dir = manager.db.get_path_mapping(
                                SOURCE_LANG, lang, source_dir
                            )
                            if target_dir:
                                target_path = str(Path(target_dir) / Path(source_file).name).replace('\\', '/')

                        if not target_path:
                            print(f"  ⊘ Skipped (no mapping): {source_file}")
                            skipped_count += 1
                            continue

                        # Check if output file exists
                        output_exists = Path(target_path).exists()

                        if output_exists:
                            # EXISTING file - check if source was modified after output
                            source_mtime = Path(source_file).stat().st_mtime
                            output_mtime = Path(target_path).stat().st_mtime

                            if source_mtime <= output_mtime:
                                # Source not modified, check if DB translations updated
                                # For simplicity, always regenerate existing files
                                # (proper implementation would track translation update times)
                                pass

                            # Regenerate existing file
                            generator.translate_file(
                                source_file, lang,
                                output_file=target_path,
                                require_mapping=False
                            )
                            print(f"  ↻ Regenerated: {target_path}")
                            regenerated_count += 1
                        else:
                            # NEW file - generate it
                            generator.translate_file(
                                source_file, lang,
                                output_file=target_path,
                                require_mapping=False
                            )
                            print(f"  ✓ Generated: {target_path}")
                            generated_count += 1

                    except Exception as e:
                        print_error(f"  ✗ Failed: {source_file} - {str(e)}")

            finally:
                generator.close()

            print_info(f"  {generated_count} new, {regenerated_count} regenerated, {skipped_count} skipped")
            print()

    finally:
        manager.close()

    return 0


def clean_pending():
    """Clean pending translations (use with caution!)"""
    output_dir = REPO_ROOT / OUTPUT_DIR
    pending_csvs = list(output_dir.glob('*.csv'))

    if not pending_csvs:
        print_info("No pending CSV files to clean")
        return 0

    print_warning(f"This will delete {len(pending_csvs)} pending CSV files in {OUTPUT_DIR}")
    response = input("Are you sure? (yes/no): ")

    if response.lower() == 'yes':
        for csv_file in pending_csvs:
            csv_file.unlink()
        print_info("Cleaned pending translations")
    else:
        print_info("Cancelled")

    return 0


def show_help():
    """Show help message"""
    help_text = f"""
Batch Translation Helper Script

Usage: python {sys.argv[0]} <command>

Commands:
  setup           - Initial setup (create path mapping template)
  import-paths    - Import path mappings from path_mappings.csv
  extract         - Extract missing translations from all files
  extract-file    - Extract missing translations from a single file
  import          - Import completed translations from CSV files
  generate        - Generate translated HTML files (all languages)
  generate-lang   - Generate HTML files for specific language
  generate-file   - Generate single translated HTML file
  overview        - Generate translation overview HTML
  stats           - Show translation statistics
  export          - Export database to JSON (backup)
  clean           - Delete pending CSV files
  help            - Show this help

Workflow:
  1. python {sys.argv[0]} setup              # Create path mapping template
  2. Edit path_mappings.csv
  3. python {sys.argv[0]} import-paths       # Import path mappings
  4. python {sys.argv[0]} extract            # Extract missing translations
  5. Edit CSV files in {OUTPUT_DIR}
  6. python {sys.argv[0]} import             # Import completed translations
  7. python {sys.argv[0]} generate           # Generate HTML files
  8. python {sys.argv[0]} overview           # View progress

Configuration:
  Source directory: {SOURCE_DIR}
  Target languages: {', '.join(TARGET_LANGS)}
  Output directory: {OUTPUT_DIR}

Examples:
  # Process a single file
  python {sys.argv[0]} extract-file en/photography/beaches.html

  # Generate HTML for specific language
  python {sys.argv[0]} generate-lang de

  # Generate single file
  python {sys.argv[0]} generate-file en/photography/beaches.html de

  # Generate overview only
  python {sys.argv[0]} overview

  # Show statistics
  python {sys.argv[0]} stats

  # Backup database
  python {sys.argv[0]} export
"""
    print(help_text)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        show_help()
        return 0

    command = sys.argv[1]

    try:
        if command == 'extract':
            return extract_all()

        elif command == 'extract-file':
            if len(sys.argv) < 3:
                print_error("Usage: python {} extract-file <file.html>".format(sys.argv[0]))
                return 1
            return extract_file(sys.argv[2])

        elif command == 'import':
            return import_translations()

        elif command == 'overview':
            generate_overview()
            return 0

        elif command == 'stats':
            show_statistics()
            return 0

        elif command == 'setup':
            return setup()

        elif command == 'import-paths':
            return import_paths()

        elif command == 'export':
            return export_database()

        elif command == 'generate':
            return generate_html_all()

        elif command == 'generate-lang':
            if len(sys.argv) < 3:
                print_error("Usage: python {} generate-lang <language_code>".format(sys.argv[0]))
                return 1
            return generate_html_all(sys.argv[2])

        elif command == 'generate-file':
            if len(sys.argv) < 4:
                print_error("Usage: python {} generate-file <source_file> <target_lang>".format(sys.argv[0]))
                return 1
            return generate_html_file(sys.argv[2], sys.argv[3])

        elif command == 'clean':
            return clean_pending()

        elif command == 'help':
            show_help()
            return 0

        else:
            print_error(f"Unknown command: {command}")
            show_help()
            return 1

    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        return 130

    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
