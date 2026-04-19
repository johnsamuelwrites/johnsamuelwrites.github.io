#!/usr/bin/env python3
"""
Translation State Management
Tracks explicit state of translation batches, CSVs, and generated files
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from enum import Enum


class BatchStatus(Enum):
    """Translation batch lifecycle states"""
    PENDING_EXTRACT = "PENDING_EXTRACT"
    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEW_APPROVED = "REVIEW_APPROVED"
    IMPORTED = "IMPORTED"
    GENERATION_COMPLETE = "GENERATION_COMPLETE"


class CSVStatus(Enum):
    """CSV file states"""
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    IMPORTED = "IMPORTED"


class QAStatus(Enum):
    """QA validation states"""
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL_EMPTY_DEST = "FAIL_EMPTY_DEST"
    FAIL_UNCHANGED_EN = "FAIL_UNCHANGED_EN"
    FAIL_PLACEHOLDER = "FAIL_PLACEHOLDER"
    FAIL_INCONSISTENT = "FAIL_INCONSISTENT"
    FAIL_ENGLISH_FALLBACK = "FAIL_ENGLISH_FALLBACK"
    FAIL_LINK_BROKEN = "FAIL_LINK_BROKEN"
    FAIL_ENTITY = "FAIL_ENTITY"


class StateManager:
    """Manage translation workflow state"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """Create state database schema if it doesn't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        # Translation batches (extract → review → import → generate)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS translation_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_dir TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # CSV files (one per batch per file)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS csv_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                csv_path TEXT NOT NULL,
                status TEXT NOT NULL,
                qa_status TEXT NOT NULL,
                qa_errors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (batch_id) REFERENCES translation_batches(batch_id),
                UNIQUE(batch_id, source_file)
            )
        ''')

        # Source file content hashes (for change detection)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_file_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Generated HTML files (output of generation)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generated_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                output_path TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                qa_status TEXT NOT NULL,
                qa_errors TEXT,
                UNIQUE(source_file, target_lang)
            )
        ''')

        self.conn.commit()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    # ===== Batch Management =====

    def create_batch(self, source_lang: str, target_lang: str, source_dir: str) -> str:
        """Create new translation batch, return batch_id"""
        batch_id = f"{target_lang}_{source_dir.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO translation_batches
            (batch_id, source_lang, target_lang, source_dir, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (batch_id, source_lang, target_lang, source_dir, BatchStatus.PENDING_EXTRACT.value))
        self.conn.commit()
        return batch_id

    def get_batch(self, batch_id: str) -> Optional[Dict]:
        """Get batch details"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM translation_batches WHERE batch_id = ?', (batch_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_batch_status(self, batch_id: str, status: BatchStatus):
        """Update batch status"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE translation_batches
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?
        ''', (status.value, batch_id))
        self.conn.commit()

    def get_batches_by_status(self, status: BatchStatus) -> List[Dict]:
        """Get all batches with given status"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM translation_batches WHERE status = ? ORDER BY created_at DESC',
            (status.value,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ===== CSV File Management =====

    def add_csv_file(self, batch_id: str, source_file: str, csv_path: str) -> None:
        """Register CSV file for a batch"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO csv_files
            (batch_id, source_file, csv_path, status, qa_status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(batch_id, source_file) DO UPDATE SET
            csv_path = excluded.csv_path,
            updated_at = CURRENT_TIMESTAMP
        ''', (batch_id, source_file, csv_path, CSVStatus.PENDING.value, QAStatus.PENDING.value))
        self.conn.commit()

    def get_csv_files(self, batch_id: str) -> List[Dict]:
        """Get all CSV files in batch"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM csv_files WHERE batch_id = ? ORDER BY source_file',
            (batch_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_csv_status(self, batch_id: str, source_file: str, status: CSVStatus):
        """Update CSV status"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE csv_files
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ? AND source_file = ?
        ''', (status.value, batch_id, source_file))
        self.conn.commit()

    def update_csv_qa(self, batch_id: str, source_file: str, qa_status: QAStatus, errors: str = None):
        """Update CSV QA status and errors"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE csv_files
            SET qa_status = ?, qa_errors = ?, updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ? AND source_file = ?
        ''', (qa_status.value, errors, batch_id, source_file))
        self.conn.commit()

    def count_csv_by_status(self, batch_id: str, status: CSVStatus) -> int:
        """Count CSVs in batch with given status"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM csv_files WHERE batch_id = ? AND status = ?',
            (batch_id, status.value)
        )
        return cursor.fetchone()[0]

    # ===== File Hash Tracking =====

    def update_file_hash(self, file_path: str, content_hash: str):
        """Update or create file hash entry"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO source_file_hashes (file_path, content_hash)
            VALUES (?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
            content_hash = excluded.content_hash,
            last_synced = CURRENT_TIMESTAMP
        ''', (file_path, content_hash))
        self.conn.commit()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get stored hash for file"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT content_hash FROM source_file_hashes WHERE file_path = ?', (file_path,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_changed_files(self, file_paths: List[str]) -> List[str]:
        """Get list of files whose hashes changed"""
        changed = []
        for file_path in file_paths:
            current_hash = self._compute_file_hash(file_path)
            stored_hash = self.get_file_hash(file_path)
            if stored_hash != current_hash:
                changed.append(file_path)
        return changed

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # ===== Generated File Tracking =====

    def add_generated_file(
        self,
        source_file: str,
        target_lang: str,
        output_path: str,
        qa_status: QAStatus = QAStatus.PENDING,
        qa_errors: str = None
    ):
        """Register generated HTML file"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO generated_files
            (source_file, target_lang, output_path, qa_status, qa_errors)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_file, target_lang) DO UPDATE SET
            output_path = excluded.output_path,
            generated_at = CURRENT_TIMESTAMP,
            qa_status = excluded.qa_status,
            qa_errors = excluded.qa_errors
        ''', (source_file, target_lang, output_path, qa_status.value, qa_errors))
        self.conn.commit()

    def update_generated_file_qa(self, source_file: str, target_lang: str, qa_status: QAStatus, errors: str = None):
        """Update QA status of generated file"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE generated_files
            SET qa_status = ?, qa_errors = ?
            WHERE source_file = ? AND target_lang = ?
        ''', (qa_status.value, errors, source_file, target_lang))
        self.conn.commit()

    def get_generated_files_by_lang(self, target_lang: str) -> List[Dict]:
        """Get all generated files for language"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM generated_files WHERE target_lang = ? ORDER BY generated_at DESC',
            (target_lang,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def count_generated_by_qa_status(self, target_lang: str, qa_status: QAStatus) -> int:
        """Count generated files with given QA status"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM generated_files WHERE target_lang = ? AND qa_status = ?',
            (target_lang, qa_status.value)
        )
        return cursor.fetchone()[0]

    # ===== Summary/Statistics =====

    def get_status_summary(self) -> Dict:
        """Get overview of current translation state"""
        cursor = self.conn.cursor()

        summary = {}
        for status in BatchStatus:
            cursor.execute(
                'SELECT COUNT(*) FROM translation_batches WHERE status = ?',
                (status.value,)
            )
            summary[f"batches_{status.value}"] = cursor.fetchone()[0]

        for lang in ['es', 'pt']:
            cursor.execute(
                'SELECT COUNT(*) FROM generated_files WHERE target_lang = ? AND qa_status = ?',
                (lang, QAStatus.PASS.value)
            )
            summary[f"generated_{lang}_pass"] = cursor.fetchone()[0]

            cursor.execute(
                'SELECT COUNT(*) FROM generated_files WHERE target_lang = ? AND qa_status LIKE ?',
                (lang, 'FAIL%')
            )
            summary[f"generated_{lang}_fail"] = cursor.fetchone()[0]

        return summary
