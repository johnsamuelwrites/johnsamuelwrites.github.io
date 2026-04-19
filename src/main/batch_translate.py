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
import csv
from pathlib import Path
from datetime import datetime
from translate_manager import TranslationManager
from html_generator import HTMLGenerator
from translation_config import (
    SOURCE_LANG,
    DEFAULT_TARGET_LANGS,
    DEFAULT_DB_PATH,
    DEFAULT_PATH_MAPPINGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_BACKUP_DIR,
    DEFAULT_GLOSSARY_DIR,
    DEFAULT_MANIFEST_DIR,
    DEFAULT_SOURCE_DIR,
)

# State database path
DEFAULT_STATE_DB_PATH = "../photography/translations_state.db"
from translation_log import backup_database, TranslationLog
from paths import REPO_ROOT


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


def extract_for_file(manager, file_path, lang, output_dir, force=False):
    """Extract translations for a single file and language"""
    basename = Path(file_path).stem
    output_csv = Path(output_dir) / f"missing_{lang}_{basename}.csv"

    result = manager.process_file(str(file_path), lang, force=force)

    if result['missing'] == 0:
        return False
    else:
        manager.export_missing_to_csv(
            result['missing_items'],
            lang,
            str(output_csv)
        )
        print_warning(f"  → {result['missing']} translations needed (saved to {output_csv})")
        return True


def cmd_setup(args):
    """Initial setup - create path mapping template"""
    print_info("Setting up translation system...")

    path_mappings_file = Path(args.paths_file)

    if path_mappings_file.exists():
        print_warning(f"{path_mappings_file} already exists")
        return 0

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        manager.create_path_mapping_template(str(path_mappings_file))
        print_info(f"Created {path_mappings_file}")
        print_info(f"Please edit {path_mappings_file} and run: python batch_translate.py import-paths")
    finally:
        manager.close()

    return 0


def cmd_import_paths(args):
    """Import path mappings from CSV"""
    path_mappings_file = Path(args.paths_file)

    if not path_mappings_file.exists():
        print_error(f"{path_mappings_file} not found")
        print_info(f"Run: python batch_translate.py setup")
        return 1

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=[],  # Not needed for import-paths, imports all mappings
        db_path=args.db_path
    )

    try:
        manager.import_path_mappings(str(path_mappings_file))
        print_info("Path mappings imported")
    finally:
        manager.close()

    return 0


def cmd_extract(args):
    """Extract translations based on path mappings in DB"""
    print_info("Starting extraction based on path mappings")
    print_info(f"Target languages: {', '.join(args.target_langs)}")
    print()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        total_missing = 0

        for lang in args.target_langs:
            print_info(f"Processing {lang}...")
            stats = manager.extract_for_language(lang, str(output_dir), force=args.force)

            if stats['total_files'] == 0:
                print_warning(f"  No path mappings for {lang}")
            else:
                print_info(f"  {stats['processed']} files, {stats['missing_count']} missing translations")
                total_missing += stats['missing_count']

            print()

        cmd_stats(args)

        if total_missing > 0:
            print_info(f"Done! Edit CSV files in {args.output_dir} and run: python batch_translate.py import")
        else:
            print_info("All mapped files are fully translated!")

    finally:
        manager.close()

    return 0


def cmd_extract_file(args):
    """Extract translations for a single file"""
    file_path = args.file
    full_path = Path(file_path)

    if not full_path.is_file():
        print_error(f"File not found: {file_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        print_info(f"Processing: {file_path}")
        has_missing = False

        for lang in args.target_langs:
            if extract_for_file(manager, file_path, lang, output_dir, force=args.force):
                has_missing = True

        if not has_missing:
            print_info(f"* File fully translated: {file_path}")

        cmd_stats(args)
    finally:
        manager.close()

    return 0


def cmd_import(args):
    """Import completed translations from CSV files"""
    print_info("Importing completed translations...")

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        output_dir = Path(args.output_dir)
        csv_files = list(output_dir.glob('*.csv'))

        if not csv_files:
            print_warning(f"No CSV files found in {args.output_dir}")
            return 0

        imported = 0
        total = len(csv_files)

        completed_dir = output_dir / 'completed'
        completed_dir.mkdir(parents=True, exist_ok=True)

        for csv_file in csv_files:
            with open(csv_file, 'r', encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))

            total_entries = len(rows)
            translated_entries = sum(
                1 for row in rows if row.get('dest_text', '').strip()
            )

            is_complete = total_entries > 0 and translated_entries == total_entries

            if is_complete:
                print_info(f"Importing: {csv_file.name} ({translated_entries}/{total_entries} translations)")
                manager.import_translations_from_csv(str(csv_file))
                imported += 1

                shutil.move(str(csv_file), str(completed_dir / csv_file.name))
            else:
                if total_entries == 0:
                    print_warning(f"Skipping (empty): {csv_file.name}")
                else:
                    print_warning(f"Skipping (incomplete): {csv_file.name} ({translated_entries}/{total_entries} translations)")

        print_info(f"Imported {imported}/{total} CSV files")

        cmd_overview(args)
        cmd_stats(args)

    finally:
        manager.close()

    return 0


def cmd_prefill(args):
    """Prefill pending translations from DB and glossary files."""
    print_info("Prefilling pending translations...")

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        output_dir = Path(args.output_dir)
        csv_files = list(output_dir.glob('*.csv'))

        if not csv_files:
            print_warning(f"No CSV files found in {args.output_dir}")
            return 0

        glossary_base = Path(args.glossary_dir)
        glossaries = {}
        for lang in args.target_langs:
            glossary_file = glossary_base / f'translation_glossary_{lang}.json'
            glossaries[lang] = manager.load_glossary(str(glossary_file))
            if glossaries[lang]:
                print_info(f"Loaded glossary for {lang}: {glossary_file.name} ({len(glossaries[lang])} entries)")
            else:
                print_warning(f"No glossary found for {lang}: {glossary_file.name}")

        total_updated = 0
        total_from_db = 0
        total_from_glossary = 0
        total_remaining = 0

        for csv_file in csv_files:
            stats = manager.prefill_translations_in_csv(
                str(csv_file),
                glossaries,
                overwrite_existing=args.overwrite
            )
            total_updated += stats['updated']
            total_from_db += stats['from_db']
            total_from_glossary += stats['from_glossary']
            total_remaining += stats['remaining']

            print_info(
                f"{csv_file.name}: updated={stats['updated']}, "
                f"db={stats['from_db']}, glossary={stats['from_glossary']}, "
                f"remaining={stats['remaining']}"
            )

        print_info(
            f"Prefill complete: updated={total_updated}, "
            f"db={total_from_db}, glossary={total_from_glossary}, remaining={total_remaining}"
        )
    finally:
        manager.close()

    return 0


def cmd_overview(args):
    """Generate translation overview HTML"""
    print_info("Generating translation overview...")

    from generate_overview import generate_overview as gen_overview

    output_path = Path('analysis/translation_overview.html')
    gen_overview(str(output_path))
    print_info(f"Overview saved to: {output_path}")


def cmd_stats(args):
    """Show translation statistics"""
    print_info("Translation Statistics:")

    output_dir = Path(args.output_dir)
    pending_csvs = list(output_dir.glob('*.csv'))
    pending = len(pending_csvs)

    completed_dir = output_dir / 'completed'
    completed = 0
    if completed_dir.is_dir():
        completed_csvs = list(completed_dir.glob('*.csv'))
        completed = len(completed_csvs)

    print(f"  Pending translations: {pending} CSV files")
    print(f"  Completed imports: {completed} CSV files")

    db_path = Path(args.db_path)
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


def cmd_completeness(args):
    """Show translation completeness per file"""
    manager = TranslationManager(
        source_lang=args.source_lang,
        db_path=args.db_path
    )

    try:
        for lang in args.target_langs:
            print_info(f"Translation completeness for {lang}:")

            files_to_process = manager.get_files_from_mappings(lang)

            if not files_to_process:
                print_warning(f"  No path mappings for {lang}")
                continue

            # Collect completeness data
            completeness_data = []
            for source_file in files_to_process:
                if not Path(source_file).exists():
                    continue

                result = manager.process_file(source_file, lang, check_existing=False, force=True)
                total = result.get('total', 0)
                found = result.get('found', 0)

                if total == 0:
                    pct = 100
                else:
                    pct = (found / total) * 100

                completeness_data.append({
                    'file': Path(source_file).name,
                    'path': source_file,
                    'total': total,
                    'found': found,
                    'pct': pct,
                })

            # Sort by chosen field
            if args.sort_by == 'percent':
                completeness_data.sort(key=lambda x: (-x['pct'], x['file']))
            elif args.sort_by == 'missing':
                completeness_data.sort(key=lambda x: (x['total'] - x['found'], x['file']))
            else:  # name
                completeness_data.sort(key=lambda x: x['file'])

            # Print results
            fully_translated = 0
            for item in completeness_data:
                pct = item['pct']
                found = item['found']
                total = item['total']
                file = item['file']

                # Create progress bar
                bar_len = 20
                filled = int(bar_len * pct / 100)
                bar = '#' * filled + '-' * (bar_len - filled)

                if pct == 100:
                    fully_translated += 1
                    status = "*"
                else:
                    status = " "

                print(f"  {status} [{bar}] {pct:5.1f}% {file:30s} ({found}/{total})")

            # Summary
            total_files = len(completeness_data)
            print_info(f"  {fully_translated}/{total_files} files fully translated")

    finally:
        manager.close()

    return 0


def cmd_export(args):
    """Export database to JSON"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"translations_backup_{timestamp}.json"

    manager = TranslationManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path
    )

    try:
        manager.db.export_to_json(output_file)
        print_info(f"Database exported to: {output_file}")
    finally:
        manager.close()

    return 0


def cmd_generate(args):
    """Generate translated HTML files for specified languages"""
    print_info(f"Generating HTML files for: {', '.join(args.target_langs)}")

    manager = TranslationManager(
        source_lang=args.source_lang,
        db_path=args.db_path
    )

    # Create backup before generation
    Path(args.backup_dir).mkdir(parents=True, exist_ok=True)
    backup_path, db_hash = backup_database(args.db_path, args.backup_dir, label="generate")
    print_info(f"Created DB backup: {backup_path}")

    # Initialize translation log
    log = TranslationLog()
    log.start_batch(args.db_path, args.source_lang, args.target_langs, args.source_dir)

    try:
        for lang in args.target_langs:
            print_info(f"Generating {lang}...")

            files_to_process = manager.get_files_from_mappings(lang)

            if not files_to_process:
                print_warning(f"  No path mappings for {lang}")
                continue

            generator = HTMLGenerator(source_lang=args.source_lang, db_path=args.db_path)
            generated_count = 0
            skipped_count = 0
            regenerated_count = 0

            try:
                for source_file in files_to_process:
                    if not Path(source_file).exists():
                        print_warning(f"  Source file not found: {source_file}")
                        continue

                    try:
                        source_path_normalized = str(Path(source_file)).replace('\\', '/')

                        target_path = manager.db.get_path_mapping(
                            args.source_lang, lang, source_path_normalized
                        )

                        if not target_path:
                            source_dir = str(Path(source_file).parent).replace('\\', '/')
                            target_dir = manager.db.get_path_mapping(
                                args.source_lang, lang, source_dir
                            )
                            if target_dir:
                                target_path = str(Path(target_dir) / Path(source_file).name).replace('\\', '/')

                        if not target_path:
                            print(f"  ⊘ Skipped (no mapping): {source_file}")
                            skipped_count += 1
                            continue

                        # Check completeness if required
                        if args.require_complete:
                            result = manager.process_file(source_file, lang, check_existing=False, force=True)
                            if result.get('missing', 0) > 0:
                                print_warning(f"  Skipping (incomplete): {source_file} "
                                            f"({result['found']}/{result['total']} translations)")
                                skipped_count += 1
                                continue

                        output_exists = Path(target_path).exists()

                        generator.translate_file(
                            source_file, lang,
                            output_file=target_path,
                            require_mapping=False,
                            force=args.force,
                            confirm=not args.force,
                        )

                        if output_exists:
                            print(f"  [REGEN] {target_path}")
                            regenerated_count += 1
                        else:
                            print(f"  [OK] {target_path}")
                            generated_count += 1

                        log.record_file(source_file, target_path, lang)

                    except Exception as e:
                        print_error(f"  [FAIL] {source_file} - {str(e)}")

            finally:
                generator.close()

            print_info(f"  {generated_count} new, {regenerated_count} regenerated, {skipped_count} skipped")

    finally:
        manager.close()

    # Finalize and write log
    log.finish_batch(backup_path, db_hash)
    Path(args.manifest_dir).mkdir(parents=True, exist_ok=True)
    manifest_path = log.write(args.manifest_dir)
    print_info(f"Translation manifest saved: {manifest_path}")

    return 0


def cmd_generate_lang(args):
    """Generate HTML files for a specific language"""
    # Override target_langs with the single specified language
    args.target_langs = [args.language]
    return cmd_generate(args)


def cmd_generate_file(args):
    """Generate single translated HTML file"""
    source_file = args.file
    target_lang = args.language

    if not Path(source_file).exists():
        print_error(f"File not found: {source_file}")
        return 1

    print_info(f"Generating {target_lang} version of {source_file}...")

    generator = HTMLGenerator(source_lang=args.source_lang, db_path=args.db_path)

    try:
        output_file = generator.translate_file(source_file, target_lang, force=args.force)
        print_info(f"✓ Generated: {output_file}")
    finally:
        generator.close()

    return 0


def cmd_clean(args):
    """Clean pending translations"""
    output_dir = Path(args.output_dir)
    pending_csvs = list(output_dir.glob('*.csv'))

    if not pending_csvs:
        print_info("No pending CSV files to clean")
        return 0

    print_warning(f"This will delete {len(pending_csvs)} pending CSV files in {args.output_dir}")
    response = input("Are you sure? (yes/no): ")

    if response.lower() == 'yes':
        for csv_file in pending_csvs:
            csv_file.unlink()
        print_info("Cleaned pending translations")
    else:
        print_info("Cancelled")

    return 0


def cmd_status(args):
    """Show translation workflow status"""
    from state_manager import StateManager

    state_mgr = StateManager(args.state_db_path)
    summary = state_mgr.get_status_summary()
    state_mgr.close()

    print_info("Translation Workflow Status")
    print("=" * 60)

    # Batch status
    print_info("Batches:")
    for status_key in ['PENDING_EXTRACT', 'PENDING_REVIEW', 'REVIEW_APPROVED', 'IMPORTED', 'GENERATION_COMPLETE']:
        count = summary.get(f"batches_{status_key}", 0)
        print(f"  {status_key}: {count}")

    # Generated files status
    print_info("Generated Files (ES):")
    pass_count = summary.get('generated_es_pass', 0)
    fail_count = summary.get('generated_es_fail', 0)
    print(f"  QA PASS: {pass_count}")
    print(f"  QA FAIL: {fail_count}")

    print_info("Generated Files (PT):")
    pass_count = summary.get('generated_pt_pass', 0)
    fail_count = summary.get('generated_pt_fail', 0)
    print(f"  QA PASS: {pass_count}")
    print(f"  QA FAIL: {fail_count}")

    return 0


def cmd_sync(args):
    """Sync translations: extract changed files with parallel processing"""
    from sync_manager import SyncManager

    sync = SyncManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path,
        state_db_path=args.state_db_path,
        max_workers=args.workers
    )

    try:
        print_info(f"Starting sync check (workers: {args.workers}, force: {args.force})")
        print_info(f"Source directory: {args.source_dir}")

        result = sync.check_and_extract(
            args.source_dir,
            args.output_dir,
            target_langs=args.target_langs,
            force=args.force
        )

        if result['status'] == 'no_files':
            print_warning("No HTML files found in source directory")
            return 0

        if result['status'] == 'no_changes':
            print_info("No changes detected in source files")
            return 0

        print_info(f"Changed files: {len(result['changed_files'])}")

        for lang, batch_info in result['extracted_batches'].items():
            if batch_info['files_extracted'] > 0:
                print_info(f"{lang}:")
                print(f"  Batch ID: {batch_info['batch_id']}")
                print(f"  Files extracted: {batch_info['files_extracted']}")
                print(f"  Translations: {batch_info['translations_count']}")
                print(f"  CSVs created: {len(batch_info['csv_files'])}")

        print_info("Sync complete. CSVs are ready for review in translations_pending/")

    finally:
        sync.close()

    return 0


def cmd_validate_csv(args):
    """Validate CSV files for translation quality"""
    from csv_validators import CSVValidator, format_validation_report, format_batch_report

    output_dir = Path(args.output_dir)
    csv_files = list(output_dir.glob('*.csv'))

    if not csv_files:
        print_warning("No CSV files found in translations_pending/")
        return 0

    print_info(f"Validating {len(csv_files)} CSV files...")

    validator = CSVValidator()
    result = validator.validate_multiple([str(f) for f in csv_files])

    # Print detailed report
    print(format_batch_report(result))

    # Print failed CSVs detailed errors
    if not result['all_valid']:
        print_error("Failed CSVs details:")
        for csv_path, validation in result['by_file'].items():
            if not validation['valid']:
                print(format_validation_report(validation, csv_path))

    return 0 if result['all_valid'] else 1


def cmd_validate_html(args):
    """Validate generated HTML files for quality issues"""
    from html_validators import HTMLValidator, format_html_batch_report, format_html_validation_report
    from pathlib import Path

    html_files = []
    for lang in args.target_langs:
        lang_dir = Path(lang) / "travel"  # Adjust if different
        if lang_dir.exists():
            html_files.extend([str(f) for f in lang_dir.rglob("*.html")])

    if not html_files:
        print_warning("No generated HTML files found")
        return 0

    print_info(f"Validating {len(html_files)} HTML files...")

    validator = HTMLValidator()
    result = validator.validate_multiple(html_files)

    # Print report
    print(format_html_batch_report(result))

    # Print failed files details
    if not result['all_valid']:
        print_error("Failed files details:")
        for html_path, validation in result['by_file'].items():
            if not validation['valid']:
                print(format_html_validation_report(validation, html_path))

    return 0 if result['all_valid'] else 1


def cmd_pipeline(args):
    """Run complete translation pipeline"""
    from pipeline_manager import PipelineManager, format_pipeline_report

    pipeline = PipelineManager(
        source_lang=args.source_lang,
        target_langs=args.target_langs,
        db_path=args.db_path,
        state_db_path=args.state_db_path,
        output_dir=args.output_dir,
        glossary_dir=args.glossary_dir,
        source_dir=args.source_dir
    )

    try:
        print_info("Starting translation pipeline...")
        print_info(f"Source dir: {args.source_dir}")
        print_info(f"Target langs: {', '.join(args.target_langs)}")

        report = pipeline.run_full_pipeline(
            force=args.force,
            auto_import=args.auto_import,
            skip_generation=args.skip_generation
        )

        # Print formatted report
        print(format_pipeline_report(report))

        return 0 if report['summary'].get('status') == 'success' else 1

    finally:
        pipeline.close()


def cmd_serve(args):
    """Start web dashboard for CSV review"""
    try:
        from web_dashboard import TranslationDashboard
    except ImportError:
        print_error("Flask not installed. Install with: pip install flask")
        return 1

    dashboard = TranslationDashboard(
        output_dir=args.output_dir,
        state_db_path=args.state_db_path,
        db_path=args.db_path,
        glossary_dir=args.glossary_dir,
        port=args.port
    )

    try:
        dashboard.run(debug=args.debug)
    except KeyboardInterrupt:
        print_info("Dashboard stopped")
    finally:
        dashboard.close()

    return 0


def cmd_glossary_sync(args):
    """Export glossaries from translation database"""
    from glossary_manager import GlossaryManager, format_glossary_export_report

    glossary_mgr = GlossaryManager(args.db_path, args.glossary_dir)

    try:
        print_info("Exporting glossaries...")

        for lang in args.target_langs:
            print_info(f"Exporting {lang}...")

            entries = glossary_mgr.get_high_value_entries(
                args.source_lang,
                lang,
                limit=200,
                min_frequency=2
            )

            if entries:
                glossary = {e['source_text']: e['target_text'] for e in entries}
                filepath = glossary_mgr.save_glossary_json(args.source_lang, lang, glossary)
                print_info(f"  Saved {len(glossary)} entries to {filepath}")
                print(format_glossary_export_report(entries))
            else:
                print_warning(f"  No entries found for {lang}")

    finally:
        glossary_mgr.close()

    return 0


def main():
    """Main entry point"""
    # Change to repo root so all paths are relative to repository
    os.chdir(REPO_ROOT)

    parser = argparse.ArgumentParser(
        description='Batch Translation Helper Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_translate.py setup
  python batch_translate.py import-paths
  python batch_translate.py extract --source-dir en/travel --target-langs es pt
  python batch_translate.py prefill --target-langs es
  python batch_translate.py import
  python batch_translate.py generate --source-dir en/travel --target-langs es pt
  python batch_translate.py stats
        """
    )

    # Global arguments
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH,
                       help=f'Path to translations.db (default: {DEFAULT_DB_PATH})')
    parser.add_argument('--source-lang', default=SOURCE_LANG,
                       help=f'Source language code (default: {SOURCE_LANG})')
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR,
                       help=f'Output directory for CSVs (default: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--paths-file', default=DEFAULT_PATH_MAPPINGS,
                       help=f'Path mappings CSV file (default: {DEFAULT_PATH_MAPPINGS})')
    parser.add_argument('--backup-dir', default=DEFAULT_BACKUP_DIR,
                       help=f'Database backups directory (default: {DEFAULT_BACKUP_DIR})')
    parser.add_argument('--manifest-dir', default=DEFAULT_MANIFEST_DIR,
                       help=f'Translation manifest directory (default: {DEFAULT_MANIFEST_DIR})')
    parser.add_argument('--glossary-dir', default=DEFAULT_GLOSSARY_DIR,
                       help=f'Glossary directory (default: {DEFAULT_GLOSSARY_DIR})')
    parser.add_argument('--state-db-path', default=DEFAULT_STATE_DB_PATH,
                       help=f'Path to state database (default: {DEFAULT_STATE_DB_PATH})')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # setup command
    subparsers.add_parser('setup', help='Create path mapping template')

    # import-paths command
    subparsers.add_parser('import-paths', help='Import path mappings from CSV')

    # extract command
    extract_parser = subparsers.add_parser('extract', help='Extract missing translations')
    extract_parser.add_argument('--source-dir', default=DEFAULT_SOURCE_DIR,
                               help=f'Source directory (default: {DEFAULT_SOURCE_DIR})')
    extract_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                               help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    extract_parser.add_argument('--force', action='store_true',
                               help='Re-extract even if files were previously processed')

    # extract-file command
    extract_file_parser = subparsers.add_parser('extract-file', help='Extract translations from single file')
    extract_file_parser.add_argument('file', help='HTML file to extract from')
    extract_file_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                    help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    extract_file_parser.add_argument('--force', action='store_true',
                                    help='Re-extract even if file was previously processed')

    # import command
    import_parser = subparsers.add_parser('import', help='Import completed translations from CSVs')
    import_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                              help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')

    # prefill command
    prefill_parser = subparsers.add_parser(
        'prefill',
        help='Prefill pending CSVs from translation DB and glossary files'
    )
    prefill_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                               help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    prefill_parser.add_argument('--overwrite', action='store_true',
                               help='Overwrite existing dest_text values if a DB/glossary match exists')

    # overview command
    subparsers.add_parser('overview', help='Generate translation overview HTML')

    # stats command
    subparsers.add_parser('stats', help='Show translation statistics')

    # completeness command
    completeness_parser = subparsers.add_parser('completeness', help='Show translation completeness per file')
    completeness_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                    help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    completeness_parser.add_argument('--sort-by', choices=['percent', 'missing', 'name'],
                                    default='percent',
                                    help='Sort order (default: percent)')

    # export command
    subparsers.add_parser('export', help='Export database to JSON')

    # generate command
    generate_parser = subparsers.add_parser('generate', help='Generate translated HTML files')
    generate_parser.add_argument('--source-dir', default=DEFAULT_SOURCE_DIR,
                                help=f'Source directory (default: {DEFAULT_SOURCE_DIR})')
    generate_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    generate_parser.add_argument('--force', action='store_true',
                                help='Regenerate even if up-to-date')
    generate_parser.add_argument('--require-complete', action='store_true',
                                help='Only generate files with 100%% translations in DB')

    # generate-lang command
    generate_lang_parser = subparsers.add_parser('generate-lang', help='Generate HTML for specific language')
    generate_lang_parser.add_argument('language', help='Language code')
    generate_lang_parser.add_argument('--source-dir', default=DEFAULT_SOURCE_DIR,
                                      help=f'Source directory (default: {DEFAULT_SOURCE_DIR})')
    generate_lang_parser.add_argument('--force', action='store_true',
                                      help='Regenerate even if up-to-date')

    # generate-file command
    generate_file_parser = subparsers.add_parser('generate-file', help='Generate single HTML file')
    generate_file_parser.add_argument('file', help='Source HTML file')
    generate_file_parser.add_argument('language', help='Target language code')
    generate_file_parser.add_argument('--force', action='store_true',
                                      help='Regenerate even if up-to-date')

    # clean command
    subparsers.add_parser('clean', help='Delete pending CSV files')

    # status command
    subparsers.add_parser('status', help='Show translation workflow status')

    # sync command
    sync_parser = subparsers.add_parser('sync', help='Sync: extract changed files with parallel processing')
    sync_parser.add_argument('--source-dir', default=DEFAULT_SOURCE_DIR,
                            help=f'Source directory (default: {DEFAULT_SOURCE_DIR})')
    sync_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                            help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    sync_parser.add_argument('--force', action='store_true',
                            help='Force extract all files, not just changed')
    sync_parser.add_argument('--workers', type=int, default=4,
                            help='Number of parallel workers (default: 4)')

    # validate-csv command
    validate_csv_parser = subparsers.add_parser('validate-csv', help='Validate CSV files for QA issues')
    validate_csv_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                    help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')

    # validate-html command
    validate_html_parser = subparsers.add_parser('validate-html', help='Validate generated HTML files')
    validate_html_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                     help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')

    # pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Run complete translation pipeline')
    pipeline_parser.add_argument('--source-dir', default=DEFAULT_SOURCE_DIR,
                               help=f'Source directory (default: {DEFAULT_SOURCE_DIR})')
    pipeline_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')
    pipeline_parser.add_argument('--force', action='store_true',
                               help='Force re-extract all files')
    pipeline_parser.add_argument('--auto-import', action='store_true',
                               help='Auto-import CSVs if validation passes')
    pipeline_parser.add_argument('--skip-generation', action='store_true',
                               help='Skip HTML generation step')

    # serve command
    serve_parser = subparsers.add_parser('serve', help='Start web dashboard for CSV review')
    serve_parser.add_argument('--port', type=int, default=8000,
                            help='Port to run dashboard on (default: 8000)')
    serve_parser.add_argument('--debug', action='store_true',
                            help='Run in debug mode')

    # glossary-sync command
    glossary_parser = subparsers.add_parser('glossary-sync', help='Export glossaries from database')
    glossary_parser.add_argument('--target-langs', nargs='+', default=DEFAULT_TARGET_LANGS,
                                help=f'Target language codes (default: {DEFAULT_TARGET_LANGS})')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == 'setup':
            return cmd_setup(args)
        elif args.command == 'import-paths':
            return cmd_import_paths(args)
        elif args.command == 'extract':
            return cmd_extract(args)
        elif args.command == 'extract-file':
            return cmd_extract_file(args)
        elif args.command == 'import':
            return cmd_import(args)
        elif args.command == 'prefill':
            return cmd_prefill(args)
        elif args.command == 'overview':
            return cmd_overview(args)
        elif args.command == 'stats':
            return cmd_stats(args)
        elif args.command == 'completeness':
            return cmd_completeness(args)
        elif args.command == 'export':
            return cmd_export(args)
        elif args.command == 'generate':
            return cmd_generate(args)
        elif args.command == 'generate-lang':
            return cmd_generate_lang(args)
        elif args.command == 'generate-file':
            return cmd_generate_file(args)
        elif args.command == 'clean':
            return cmd_clean(args)
        elif args.command == 'status':
            return cmd_status(args)
        elif args.command == 'sync':
            return cmd_sync(args)
        elif args.command == 'validate-csv':
            return cmd_validate_csv(args)
        elif args.command == 'validate-html':
            return cmd_validate_html(args)
        elif args.command == 'pipeline':
            return cmd_pipeline(args)
        elif args.command == 'serve':
            return cmd_serve(args)
        elif args.command == 'glossary-sync':
            return cmd_glossary_sync(args)
        else:
            print_error(f"Unknown command: {args.command}")
            parser.print_help()
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
