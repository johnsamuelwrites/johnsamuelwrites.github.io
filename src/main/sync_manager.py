#!/usr/bin/env python3
"""
Translation Sync Manager
Handles sync loop: extract changed files, prefill, track state
Supports parallel processing of multiple files and languages
"""

import os
from pathlib import Path
from typing import List, Dict, Set, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

from state_manager import StateManager, BatchStatus, CSVStatus, QAStatus
from translate_manager import TranslationManager


class SyncManager:
    """Manage translation sync operations"""

    def __init__(
        self,
        source_lang: str = "en",
        target_langs: List[str] = None,
        db_path: str = None,
        state_db_path: str = None,
        max_workers: int = 4
    ):
        self.source_lang = source_lang
        self.target_langs = target_langs or ["es", "pt"]
        self.db_path = db_path
        self.state_db_path = state_db_path
        self.max_workers = max_workers

        self.state_mgr = StateManager(state_db_path)
        self.trans_mgr = TranslationManager(
            source_lang=source_lang,
            target_langs=target_langs,
            db_path=db_path
        )

    def close(self):
        """Close database connections"""
        self.state_mgr.close()
        self.trans_mgr.close()

    def get_source_files(self, source_dir: str) -> List[str]:
        """Get all HTML files in source directory"""
        path = Path(source_dir)
        if not path.exists():
            return []
        return sorted([str(f) for f in path.rglob("*.html")])

    def check_and_extract(
        self,
        source_dir: str,
        output_dir: str,
        target_langs: List[str] = None,
        force: bool = False
    ) -> Dict[str, any]:
        """
        Check for changed source files and extract translations
        Uses parallel processing for multiple files
        Returns: summary of what was extracted
        """
        target_langs = target_langs or self.target_langs

        # Get all source files
        all_files = self.get_source_files(source_dir)
        if not all_files:
            return {
                'status': 'no_files',
                'changed_files': [],
                'extracted_batches': {}
            }

        # Determine which files changed
        if force:
            changed_files = all_files
        else:
            changed_files = self._detect_changed_files(all_files)

        if not changed_files:
            return {
                'status': 'no_changes',
                'changed_files': [],
                'extracted_batches': {}
            }

        # Update hashes for all files
        for file_path in all_files:
            hash_val = self._compute_file_hash(file_path)
            self.state_mgr.update_file_hash(file_path, hash_val)

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Extract in parallel
        extracted_batches = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for lang in target_langs:
                batch_id = self.state_mgr.create_batch(self.source_lang, lang, source_dir)
                extracted_batches[lang] = {
                    'batch_id': batch_id,
                    'files_extracted': 0,
                    'translations_count': 0,
                    'csv_files': []
                }

                for file_path in changed_files:
                    future = executor.submit(
                        self._extract_and_prefill,
                        file_path,
                        lang,
                        batch_id,
                        output_dir
                    )
                    futures[future] = (lang, file_path, batch_id)

            # Collect results
            for future in as_completed(futures):
                lang, file_path, batch_id = futures[future]
                try:
                    result = future.result()
                    if result['extracted']:
                        extracted_batches[lang]['files_extracted'] += 1
                        extracted_batches[lang]['translations_count'] += result['translation_count']
                        extracted_batches[lang]['csv_files'].append(result['csv_path'])
                except Exception as e:
                    print(f"Error extracting {file_path} for {lang}: {e}")

        # Update batch status
        for lang, batch_info in extracted_batches.items():
            if batch_info['files_extracted'] > 0:
                self.state_mgr.update_batch_status(batch_info['batch_id'], BatchStatus.PENDING_REVIEW)

        return {
            'status': 'success',
            'changed_files': changed_files,
            'extracted_batches': extracted_batches
        }

    def _detect_changed_files(self, file_paths: List[str]) -> List[str]:
        """Detect which files have changed since last sync"""
        changed = []
        for file_path in file_paths:
            current_hash = self._compute_file_hash(file_path)
            stored_hash = self.state_mgr.get_file_hash(file_path)
            if stored_hash != current_hash:
                changed.append(file_path)
        return changed

    def _extract_and_prefill(
        self,
        file_path: str,
        lang: str,
        batch_id: str,
        output_dir: str
    ) -> Dict:
        """Extract translations from file and prefill from glossary"""
        try:
            # Create new TranslationManager for this thread (SQLite thread-safety)
            trans_mgr = TranslationManager(
                source_lang=self.source_lang,
                target_langs=[lang],
                db_path=self.db_path
            )

            result = trans_mgr.process_file(file_path, lang, force=True)

            if result['missing'] == 0:
                trans_mgr.close()
                return {'extracted': False, 'translation_count': 0}

            # Export to CSV
            csv_name = Path(file_path).stem
            csv_path = str(Path(output_dir) / f"missing_{lang}_{csv_name}.csv")

            trans_mgr.export_missing_to_csv(result['missing_items'], lang, csv_path)

            # Register in state DB (create thread-local state manager)
            state_mgr = StateManager(self.state_db_path)
            try:
                state_mgr.add_csv_file(batch_id, file_path, csv_path)
            finally:
                state_mgr.close()

            # Prefill from glossary
            glossary = trans_mgr.load_glossary(f"../photography/translation_glossary_{lang}.json")
            if glossary:
                prefill_stats = trans_mgr.prefill_translations_in_csv(csv_path, {lang: glossary})
            else:
                prefill_stats = {'updated': 0, 'from_db': 0, 'from_glossary': 0, 'remaining': result['missing']}

            trans_mgr.close()

            return {
                'extracted': True,
                'translation_count': result['missing'],
                'csv_path': csv_path,
                'prefilled': prefill_stats
            }
        except Exception as e:
            print(f"Error in _extract_and_prefill for {file_path}: {e}")
            return {'extracted': False, 'translation_count': 0, 'error': str(e)}

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
        except Exception:
            return ""
        return sha256_hash.hexdigest()

    def regenerate_for_language(
        self,
        target_lang: str,
        source_dir: str,
        state_only: bool = False
    ) -> Dict:
        """
        Regenerate HTML files for a language after translations imported
        Only regenerates files that have been fully translated
        Returns: summary of generation results
        """
        files_to_process = self.trans_mgr.get_files_from_mappings(target_lang)

        if not files_to_process:
            return {
                'status': 'no_mappings',
                'generated': 0,
                'regenerated': 0,
                'skipped': 0
            }

        from html_generator import HTMLGenerator

        generator = HTMLGenerator(source_lang=self.source_lang, db_path=self.db_path)
        generated = 0
        regenerated = 0
        skipped = 0

        try:
            for source_file in files_to_process:
                if not Path(source_file).exists():
                    skipped += 1
                    continue

                try:
                    source_path_normalized = str(Path(source_file)).replace('\\', '/')
                    target_path = self.trans_mgr.db.get_path_mapping(
                        self.source_lang, target_lang, source_path_normalized
                    )

                    if not target_path:
                        source_dir_path = str(Path(source_file).parent).replace('\\', '/')
                        target_dir = self.trans_mgr.db.get_path_mapping(
                            self.source_lang, target_lang, source_dir_path
                        )
                        if target_dir:
                            target_path = str(Path(target_dir) / Path(source_file).name).replace('\\', '/')

                    if not target_path:
                        skipped += 1
                        continue

                    # Check completeness
                    result = self.trans_mgr.process_file(source_file, target_lang, check_existing=False, force=True)
                    if result.get('missing', 0) > 0:
                        skipped += 1
                        continue

                    # Generate
                    output_exists = Path(target_path).exists()
                    if not state_only:
                        generator.translate_file(
                            source_file,
                            target_lang,
                            output_file=target_path,
                            require_mapping=False,
                            force=True,
                            confirm=False
                        )

                    # Track in state
                    self.state_mgr.add_generated_file(source_file, target_lang, target_path)

                    if output_exists:
                        regenerated += 1
                    else:
                        generated += 1

                except Exception as e:
                    print(f"Error generating {source_file}: {e}")
                    skipped += 1

        finally:
            generator.close()

        return {
            'status': 'success',
            'generated': generated,
            'regenerated': regenerated,
            'skipped': skipped
        }

    def get_status_summary(self) -> Dict:
        """Get current translation state summary"""
        return self.state_mgr.get_status_summary()
