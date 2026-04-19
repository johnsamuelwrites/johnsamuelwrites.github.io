#!/usr/bin/env python3
"""
Glossary Management
Auto-export translations from completed files, manage glossary entries
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict


class GlossaryManager:
    """Manage translation glossaries"""

    def __init__(self, db_path: str, glossary_dir: str):
        self.db_path = db_path
        self.glossary_dir = Path(glossary_dir)
        self.conn = None
        self._connect()

    def _connect(self):
        """Connect to translation database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def export_glossary(self, source_lang: str, target_lang: str, min_frequency: int = 2) -> Dict[str, str]:
        """
        Export glossary from translation database
        Only includes translations that appear multiple times (high reuse)
        Returns: {source_text: target_text, ...}
        """
        cursor = self.conn.cursor()

        # Get all translations for this language pair
        cursor.execute('''
            SELECT source_text, target_text, COUNT(*) as frequency
            FROM translations
            WHERE source_lang = ? AND target_lang = ?
            GROUP BY source_text, target_text
            HAVING frequency >= ?
            ORDER BY frequency DESC
        ''', (source_lang, target_lang, min_frequency))

        glossary = {}
        for row in cursor.fetchall():
            source_text = row['source_text']
            target_text = row['target_text']
            glossary[source_text] = target_text

        return glossary

    def save_glossary_json(
        self,
        source_lang: str,
        target_lang: str,
        glossary: Dict[str, str],
        filename: str = None
    ) -> str:
        """
        Save glossary to JSON file
        Format: {"source_text": "target_text", ...}
        """
        if filename is None:
            filename = f"translation_glossary_{target_lang}.json"

        output_path = self.glossary_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)

        return str(output_path)

    def extract_from_generated(
        self,
        source_lang: str,
        target_lang: str,
        min_frequency: int = 2
    ) -> Dict[str, Tuple[str, int]]:
        """
        Extract glossary entries from completed translations
        Returns: {source_text: (target_text, frequency), ...}
        """
        cursor = self.conn.cursor()

        # Get all translations with frequency
        cursor.execute('''
            SELECT source_text, target_text, COUNT(*) as frequency
            FROM translations
            WHERE source_lang = ? AND target_lang = ?
            GROUP BY source_text, target_text
            HAVING frequency >= ?
            ORDER BY frequency DESC
        ''', (source_lang, target_lang, min_frequency))

        entries = {}
        for row in cursor.fetchall():
            source_text = row['source_text']
            target_text = row['target_text']
            frequency = row['frequency']
            entries[source_text] = (target_text, frequency)

        return entries

    def get_high_value_entries(
        self,
        source_lang: str,
        target_lang: str,
        limit: int = 100,
        min_frequency: int = 2
    ) -> List[Dict]:
        """
        Get high-value glossary entries (most frequently used)
        Returns list sorted by frequency descending
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT source_text, target_text, COUNT(*) as frequency
            FROM translations
            WHERE source_lang = ? AND target_lang = ?
            GROUP BY source_text, target_text
            HAVING frequency >= ?
            ORDER BY frequency DESC
            LIMIT ?
        ''', (source_lang, target_lang, min_frequency, limit))

        entries = []
        for row in cursor.fetchall():
            entries.append({
                'source_text': row['source_text'],
                'target_text': row['target_text'],
                'frequency': row['frequency']
            })

        return entries

    def load_glossary_json(self, filepath: str) -> Dict[str, str]:
        """Load glossary from JSON file"""
        path = Path(filepath)
        if not path.exists():
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading glossary {filepath}: {e}")
            return {}

    def get_all_glossaries(self) -> Dict[str, str]:
        """Get all glossary files in glossary directory"""
        glossaries = {}
        for json_file in self.glossary_dir.glob("translation_glossary_*.json"):
            lang = json_file.stem.replace("translation_glossary_", "")
            glossaries[lang] = str(json_file)
        return glossaries

    def merge_glossaries(self, glossary1: Dict[str, str], glossary2: Dict[str, str]) -> Dict[str, str]:
        """
        Merge two glossaries
        glossary2 overwrites glossary1 for duplicate entries
        """
        merged = glossary1.copy()
        merged.update(glossary2)
        return merged

    def get_missing_translations_for_context(
        self,
        source_lang: str,
        target_lang: str,
        source_text: str,
        context: str = None
    ) -> List[str]:
        """
        Get all translations for a source_text with given context
        Useful for context-aware translation suggestions
        """
        cursor = self.conn.cursor()

        if context:
            cursor.execute('''
                SELECT DISTINCT target_text
                FROM translations
                WHERE source_lang = ? AND target_lang = ? AND source_text = ? AND context = ?
                ORDER BY rowid DESC
            ''', (source_lang, target_lang, source_text, context))
        else:
            cursor.execute('''
                SELECT DISTINCT target_text
                FROM translations
                WHERE source_lang = ? AND target_lang = ? AND source_text = ?
                ORDER BY rowid DESC
            ''', (source_lang, target_lang, source_text))

        return [row[0] for row in cursor.fetchall()]

    def get_context_aware_glossary(
        self,
        source_lang: str,
        target_lang: str,
        min_frequency: int = 1
    ) -> Dict[Tuple[str, str], str]:
        """
        Get glossary with context awareness
        Returns: {(source_text, context): target_text, ...}
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT source_text, context, target_text, COUNT(*) as frequency
            FROM translations
            WHERE source_lang = ? AND target_lang = ?
            GROUP BY source_text, context, target_text
            HAVING frequency >= ?
            ORDER BY frequency DESC
        ''', (source_lang, target_lang, min_frequency))

        glossary = {}
        for row in cursor.fetchall():
            key = (row['source_text'], row['context'] or '')
            glossary[key] = row['target_text']

        return glossary

    def suggest_translation(
        self,
        source_lang: str,
        target_lang: str,
        source_text: str,
        context: str = None,
        threshold: float = 0.8
    ) -> List[Tuple[str, float]]:
        """
        Suggest translations based on similarity to existing translations
        Returns: [(suggested_text, confidence), ...]
        """
        cursor = self.conn.cursor()

        # Get all translations for this source text
        if context:
            cursor.execute('''
                SELECT target_text, COUNT(*) as frequency
                FROM translations
                WHERE source_lang = ? AND target_lang = ? AND source_text = ? AND context = ?
                GROUP BY target_text
                ORDER BY frequency DESC
            ''', (source_lang, target_lang, source_text, context))
        else:
            cursor.execute('''
                SELECT target_text, COUNT(*) as frequency
                FROM translations
                WHERE source_lang = ? AND target_lang = ? AND source_text = ?
                GROUP BY target_text
                ORDER BY frequency DESC
            ''', (source_lang, target_lang, source_text))

        suggestions = []
        rows = cursor.fetchall()
        total = sum(r['frequency'] for r in rows) if rows else 1

        for row in rows:
            confidence = row['frequency'] / total
            if confidence >= threshold:
                suggestions.append((row['target_text'], confidence))

        return suggestions


def format_glossary_export_report(entries: List[Dict]) -> str:
    """Format glossary export as readable report"""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("GLOSSARY EXPORT REPORT")
    lines.append("=" * 80)

    lines.append(f"\nTotal entries: {len(entries)}")

    if entries:
        lines.append("\nTop 20 entries (by frequency):")
        for i, entry in enumerate(entries[:20], 1):
            source = entry['source_text'][:40]
            target = entry['target_text'][:40]
            freq = entry['frequency']
            lines.append(f"  {i:2d}. [{freq:3d}x] {source:40s} => {target}")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)
