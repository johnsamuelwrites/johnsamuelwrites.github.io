#!/usr/bin/env python3
"""
Translation Pipeline Manager
Orchestrates complete workflow: sync → review → validate → import → generate → export glossary
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from sync_manager import SyncManager
from state_manager import StateManager, BatchStatus, QAStatus
from csv_validators import CSVValidator, format_batch_report
from html_validators import HTMLValidator, format_html_batch_report
from glossary_manager import GlossaryManager, format_glossary_export_report
from translate_manager import TranslationManager


class PipelineManager:
    """Orchestrate complete translation workflow"""

    def __init__(
        self,
        source_lang: str = "en",
        target_langs: List[str] = None,
        db_path: str = None,
        state_db_path: str = None,
        output_dir: str = None,
        glossary_dir: str = None,
        source_dir: str = None,
    ):
        self.source_lang = source_lang
        self.target_langs = target_langs or ["es", "pt"]
        self.db_path = db_path
        self.state_db_path = state_db_path
        self.output_dir = Path(output_dir) if output_dir else Path("translations_pending")
        self.glossary_dir = glossary_dir
        self.source_dir = source_dir

        self.sync_mgr = SyncManager(
            source_lang=source_lang,
            target_langs=target_langs,
            db_path=db_path,
            state_db_path=state_db_path
        )
        self.state_mgr = StateManager(state_db_path)
        self.csv_validator = CSVValidator()
        self.html_validator = HTMLValidator()
        self.glossary_mgr = GlossaryManager(db_path, glossary_dir)

    def close(self):
        """Close all database connections"""
        self.sync_mgr.close()
        self.state_mgr.close()
        self.glossary_mgr.close()

    def run_full_pipeline(
        self,
        force: bool = False,
        auto_import: bool = False,
        skip_generation: bool = False
    ) -> Dict:
        """
        Run complete pipeline:
        1. Sync (extract changed files)
        2. Validate CSVs (pre-import QA)
        3. Import (if QA passes and auto_import=True)
        4. Generate (regenerate affected files)
        5. Validate HTML (post-gen QA)
        6. Export glossary (for next cycle)

        Returns detailed report of all steps
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'sync': None,
            'csv_validation': None,
            'import': None,
            'generation': None,
            'html_validation': None,
            'glossary_export': None,
            'summary': {}
        }

        # Step 1: Sync
        print("[PIPELINE] Step 1/6: Syncing translations...")
        sync_result = self.sync_mgr.check_and_extract(
            self.source_dir,
            str(self.output_dir),
            target_langs=self.target_langs,
            force=force
        )
        report['sync'] = sync_result

        if sync_result['status'] == 'no_changes':
            print("[PIPELINE] No changes detected. Pipeline aborted.")
            report['summary']['status'] = 'no_changes'
            return report

        # Step 2: Validate CSVs
        print("[PIPELINE] Step 2/6: Validating CSV files...")
        csv_files = list(self.output_dir.glob('*.csv'))
        if csv_files:
            csv_validation = self.csv_validator.validate_multiple([str(f) for f in csv_files])
            report['csv_validation'] = csv_validation

            if not csv_validation['all_valid']:
                print("[PIPELINE] CSV validation failed. Please fix errors and retry.")
                report['summary']['status'] = 'csv_validation_failed'
                print(format_batch_report(csv_validation))
                return report
        else:
            print("[PIPELINE] No CSVs to validate (all files already translated)")

        # Step 3: Import
        if auto_import or self._prompt_for_import():
            print("[PIPELINE] Step 3/6: Importing translations...")
            import_result = self._import_translations()
            report['import'] = import_result

            if not import_result['success']:
                print("[PIPELINE] Import failed. Check errors above.")
                report['summary']['status'] = 'import_failed'
                return report
        else:
            print("[PIPELINE] Import skipped. Run manually when ready.")
            report['summary']['status'] = 'awaiting_import'
            return report

        # Step 4: Generate
        if skip_generation:
            print("[PIPELINE] Generation skipped (--skip-generation)")
        else:
            print("[PIPELINE] Step 4/6: Generating HTML files...")
            generation_result = self._generate_html()
            report['generation'] = generation_result

        # Step 5: Validate HTML
        print("[PIPELINE] Step 5/6: Validating generated HTML...")
        html_files = self._get_generated_html_files()
        if html_files:
            html_validation = self.html_validator.validate_multiple(html_files)
            report['html_validation'] = html_validation

            if not html_validation['all_valid']:
                print("[PIPELINE] HTML validation found issues:")
                print(format_html_batch_report(html_validation))
        else:
            print("[PIPELINE] No generated HTML files to validate")

        # Step 6: Export Glossary
        print("[PIPELINE] Step 6/6: Exporting glossary for next cycle...")
        glossary_result = self._export_glossaries()
        report['glossary_export'] = glossary_result

        # Summary
        report['summary'] = self._compile_summary(report)
        print("[PIPELINE] Pipeline complete!")

        return report

    def _prompt_for_import(self) -> bool:
        """Prompt user before importing"""
        csv_files = list(self.output_dir.glob('*.csv'))
        if not csv_files:
            return False
        print(f"\nFound {len(csv_files)} validated CSVs ready for import.")
        response = input("Import now? (yes/no): ").lower().strip()
        return response in ['yes', 'y']

    def _import_translations(self) -> Dict:
        """Import completed CSVs into database"""
        trans_mgr = TranslationManager(
            source_lang=self.source_lang,
            target_langs=self.target_langs,
            db_path=self.db_path
        )

        try:
            csv_files = list(self.output_dir.glob('*.csv'))
            imported = 0
            failed = 0
            errors = []

            completed_dir = self.output_dir / 'completed'
            completed_dir.mkdir(parents=True, exist_ok=True)

            for csv_file in csv_files:
                try:
                    trans_mgr.import_translations_from_csv(str(csv_file))
                    csv_file.rename(completed_dir / csv_file.name)
                    imported += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))

            return {
                'success': failed == 0,
                'imported': imported,
                'failed': failed,
                'errors': errors
            }
        finally:
            trans_mgr.close()

    def _generate_html(self) -> Dict:
        """Regenerate HTML files for all languages"""
        from html_generator import HTMLGenerator

        results = {}
        for lang in self.target_langs:
            generator = HTMLGenerator(source_lang=self.source_lang, db_path=self.db_path)
            try:
                files_to_process = self.sync_mgr.trans_mgr.get_files_from_mappings(lang)
                generated = 0
                regenerated = 0
                skipped = 0

                for source_file in files_to_process:
                    if not Path(source_file).exists():
                        skipped += 1
                        continue

                    try:
                        source_path_normalized = str(Path(source_file)).replace('\\', '/')
                        target_path = self.sync_mgr.trans_mgr.db.get_path_mapping(
                            self.source_lang, lang, source_path_normalized
                        )

                        if not target_path:
                            source_dir_path = str(Path(source_file).parent).replace('\\', '/')
                            target_dir = self.sync_mgr.trans_mgr.db.get_path_mapping(
                                self.source_lang, lang, source_dir_path
                            )
                            if target_dir:
                                target_path = str(Path(target_dir) / Path(source_file).name).replace('\\', '/')

                        if not target_path:
                            skipped += 1
                            continue

                        # Check completeness
                        result = self.sync_mgr.trans_mgr.process_file(
                            source_file, lang, check_existing=False, force=True
                        )
                        if result.get('missing', 0) > 0:
                            skipped += 1
                            continue

                        # Generate
                        output_exists = Path(target_path).exists()
                        generator.translate_file(
                            source_file,
                            lang,
                            output_file=target_path,
                            require_mapping=False,
                            force=True,
                            confirm=False
                        )

                        self.state_mgr.add_generated_file(source_file, lang, target_path)

                        if output_exists:
                            regenerated += 1
                        else:
                            generated += 1

                    except Exception as e:
                        print(f"Error generating {source_file}: {e}")
                        skipped += 1

                results[lang] = {
                    'generated': generated,
                    'regenerated': regenerated,
                    'skipped': skipped
                }

            finally:
                generator.close()

        return results

    def _get_generated_html_files(self) -> List[str]:
        """Get all generated HTML files"""
        html_files = []
        for lang in self.target_langs:
            lang_dir = Path(lang)
            if lang_dir.exists():
                html_files.extend([str(f) for f in lang_dir.rglob("*.html")])
        return html_files

    def _export_glossaries(self) -> Dict:
        """Export glossaries for each language"""
        results = {}

        for lang in self.target_langs:
            try:
                # Get high-value entries
                entries = self.glossary_mgr.get_high_value_entries(
                    self.source_lang,
                    lang,
                    limit=200,
                    min_frequency=2
                )

                if entries:
                    # Create glossary dict
                    glossary = {e['source_text']: e['target_text'] for e in entries}

                    # Save to file
                    filepath = self.glossary_mgr.save_glossary_json(
                        self.source_lang,
                        lang,
                        glossary
                    )

                    results[lang] = {
                        'success': True,
                        'entries': len(glossary),
                        'path': filepath
                    }
                else:
                    results[lang] = {
                        'success': True,
                        'entries': 0,
                        'path': None
                    }

            except Exception as e:
                results[lang] = {
                    'success': False,
                    'error': str(e)
                }

        return results

    def _compile_summary(self, report: Dict) -> Dict:
        """Compile final summary from all pipeline steps"""
        summary = {
            'status': 'success',
            'timestamp': report['timestamp'],
            'sync': {},
            'csv_validation': {},
            'import': {},
            'generation': {},
            'html_validation': {},
            'glossary': {}
        }

        # Sync summary
        if report['sync']:
            summary['sync'] = {
                'status': report['sync'].get('status'),
                'changed_files': len(report['sync'].get('changed_files', [])),
                'batches': len(report['sync'].get('extracted_batches', {}))
            }

        # CSV validation summary
        if report['csv_validation']:
            summary['csv_validation'] = {
                'all_valid': report['csv_validation']['all_valid'],
                'errors': report['csv_validation'].get('total_critical_errors', 0)
            }

        # Import summary
        if report['import']:
            summary['import'] = {
                'imported': report['import'].get('imported', 0),
                'failed': report['import'].get('failed', 0)
            }

        # Generation summary
        if report['generation']:
            summary['generation'] = report['generation']

        # HTML validation summary
        if report['html_validation']:
            summary['html_validation'] = {
                'all_valid': report['html_validation']['all_valid'],
                'errors': report['html_validation'].get('total_errors', 0)
            }

        # Glossary summary
        if report['glossary_export']:
            summary['glossary'] = {
                lang: {
                    'entries': data.get('entries', 0),
                    'success': data.get('success', False)
                }
                for lang, data in report['glossary_export'].items()
            }

        return summary


def format_pipeline_report(report: Dict) -> str:
    """Format pipeline report as readable output"""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("TRANSLATION PIPELINE REPORT")
    lines.append("=" * 80)

    summary = report.get('summary', {})
    timestamp = summary.get('timestamp', '')
    lines.append(f"\nTimestamp: {timestamp}")

    # Sync
    if summary.get('sync'):
        lines.append(f"\n[SYNC]")
        lines.append(f"  Status: {summary['sync'].get('status')}")
        lines.append(f"  Changed files: {summary['sync'].get('changed_files')}")
        lines.append(f"  Batches: {summary['sync'].get('batches')}")

    # CSV Validation
    if summary.get('csv_validation'):
        csv_status = "[PASS]" if summary['csv_validation']['all_valid'] else "[FAIL]"
        lines.append(f"\n[CSV VALIDATION] {csv_status}")
        lines.append(f"  Errors: {summary['csv_validation'].get('errors')}")

    # Import
    if summary.get('import'):
        lines.append(f"\n[IMPORT]")
        lines.append(f"  Imported: {summary['import'].get('imported')}")
        lines.append(f"  Failed: {summary['import'].get('failed')}")

    # Generation
    if summary.get('generation'):
        lines.append(f"\n[GENERATION]")
        for lang, stats in summary['generation'].items():
            lines.append(f"  {lang}:")
            lines.append(f"    Generated: {stats.get('generated')}")
            lines.append(f"    Regenerated: {stats.get('regenerated')}")
            lines.append(f"    Skipped: {stats.get('skipped')}")

    # HTML Validation
    if summary.get('html_validation'):
        html_status = "[PASS]" if summary['html_validation']['all_valid'] else "[FAIL]"
        lines.append(f"\n[HTML VALIDATION] {html_status}")
        lines.append(f"  Errors: {summary['html_validation'].get('errors')}")

    # Glossary
    if summary.get('glossary'):
        lines.append(f"\n[GLOSSARY EXPORT]")
        for lang, stats in summary['glossary'].items():
            status = "[OK]" if stats.get('success') else "[FAIL]"
            lines.append(f"  {lang} {status}: {stats.get('entries')} entries")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)
