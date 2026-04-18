"""
Translation batch logging and database backup system.
Provides reproducibility by recording DB version and backup path for each translation batch.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def backup_database(db_path: str, backup_dir: str, label: str = "backup") -> tuple[str, str]:
    """
    Create timestamped backup of translation database.

    Args:
        db_path: Path to translations.db
        backup_dir: Directory to store backup
        label: Label for backup (e.g., 'generate', 'extract')

    Returns:
        Tuple of (backup_path, sha256_hash)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"translations_{timestamp}_{label}.db"
    backup_path = Path(backup_dir) / backup_name

    Path(backup_dir).mkdir(parents=True, exist_ok=True)

    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    shutil.copy2(db_path, backup_path)

    db_hash = hashlib.sha256(Path(db_path).read_bytes()).hexdigest()

    return str(backup_path), db_hash


class TranslationLog:
    """Log translations for a batch (reproducibility tracking)."""

    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.db_path = None
        self.db_hash = None
        self.backup_path = None
        self.source_lang = None
        self.target_langs = []
        self.source_dir = None
        self.files = []

    def start_batch(self, db_path: str, source_lang: str, target_langs: List[str], source_dir: str):
        """Initialize batch logging."""
        self.db_path = db_path
        self.source_lang = source_lang
        self.target_langs = target_langs
        self.source_dir = source_dir

    def record_file(self, source_file: str, output_file: str, target_lang: str):
        """Record a generated file."""
        self.files.append({
            "source": source_file,
            "output": output_file,
            "target_lang": target_lang
        })

    def finish_batch(self, backup_path: str, db_hash: str):
        """Finalize batch with backup info."""
        self.backup_path = backup_path
        self.db_hash = db_hash

    def to_dict(self) -> Dict:
        """Convert log to dictionary."""
        return {
            "timestamp": self.timestamp,
            "db_path": self.db_path,
            "db_hash": f"sha256:{self.db_hash}" if self.db_hash else None,
            "backup_path": self.backup_path,
            "source_lang": self.source_lang,
            "target_langs": self.target_langs,
            "source_dir": self.source_dir,
            "files": self.files
        }

    def write(self, manifest_dir: str) -> str:
        """
        Write manifest JSON to disk.

        Args:
            manifest_dir: Directory for manifest files

        Returns:
            Path to written manifest file
        """
        Path(manifest_dir).mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest_path = Path(manifest_dir) / f"manifest_{timestamp_str}.json"

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return str(manifest_path)
