#!/usr/bin/env python3
"""
CSV Translation Quality Assurance
Validates translations before import
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
from translate_manager import normalize_translation_text


class CSVValidationError:
    """Represents a validation error in a CSV file"""

    def __init__(self, line_num: int, error_type: str, message: str, row_data: Dict = None):
        self.line_num = line_num
        self.error_type = error_type
        self.message = message
        self.row_data = row_data or {}

    def __repr__(self):
        return f"Line {self.line_num}: [{self.error_type}] {self.message}"


class CSVValidator:
    """Validate translation CSVs for quality issues"""

    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_WARNING = "WARNING"

    def __init__(self):
        self.errors: List[CSVValidationError] = []
        self.translation_map: Dict[tuple, str] = {}  # (source_text, context) → dest_text

    def validate_file(self, csv_path: str) -> Dict:
        """
        Validate a single CSV file
        Returns: {
            'valid': bool,
            'errors': List[CSVValidationError],
            'critical_count': int,
            'warning_count': int
        }
        """
        self.errors = []
        self.translation_map = {}

        path = Path(csv_path)
        if not path.exists():
            return {
                'valid': False,
                'errors': [CSVValidationError(0, 'FILE_NOT_FOUND', f'CSV file not found: {csv_path}')],
                'critical_count': 1,
                'warning_count': 0
            }

        try:
            with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or 'source_text' not in reader.fieldnames:
                    return {
                        'valid': False,
                        'errors': [CSVValidationError(0, 'INVALID_HEADER', 'CSV missing required headers')],
                        'critical_count': 1,
                        'warning_count': 0
                    }

                for line_num, row in enumerate(reader, start=2):
                    self._validate_row(row, line_num)

        except Exception as e:
            self.errors.append(CSVValidationError(0, 'READ_ERROR', f'Error reading CSV: {str(e)}'))

        critical_count = sum(1 for e in self.errors if e.error_type.startswith('FAIL'))
        warning_count = len(self.errors) - critical_count

        return {
            'valid': critical_count == 0,
            'errors': self.errors,
            'critical_count': critical_count,
            'warning_count': warning_count
        }

    def _validate_row(self, row: Dict, line_num: int):
        """Validate a single CSV row"""
        source_text = row.get('source_text', '').strip()
        dest_text = row.get('dest_text', '').strip()
        context = row.get('context', '').strip()

        # ===== CRITICAL: Empty destination =====
        if not dest_text:
            self.errors.append(CSVValidationError(
                line_num,
                'FAIL_EMPTY_DEST',
                f'Empty dest_text: "{source_text[:50]}"',
                row
            ))
            return

        # ===== CRITICAL: Unchanged English =====
        if self._is_unchanged_english(source_text, dest_text):
            self.errors.append(CSVValidationError(
                line_num,
                'FAIL_UNCHANGED_EN',
                f'dest_text is identical to source_text: "{source_text[:50]}"',
                row
            ))

        # ===== CRITICAL: Broken placeholders =====
        self._check_placeholders(source_text, dest_text, line_num, row)

        # ===== CRITICAL: Inconsistent translations =====
        self._check_consistency(source_text, dest_text, context, line_num, row)

    def _is_unchanged_english(self, source: str, dest: str) -> bool:
        """Check if destination is identical to source (no translation done)"""
        source_norm = normalize_translation_text(source)
        dest_norm = normalize_translation_text(dest)
        return source_norm == dest_norm and source_norm  # Must be non-empty

    def _check_placeholders(self, source: str, dest: str, line_num: int, row: Dict):
        """Check for broken placeholders like {name}, {year}"""
        import re

        source_placeholders = set(re.findall(r'\{(\w+)\}', source))
        dest_placeholders = set(re.findall(r'\{(\w+)\}', dest))

        # If source has placeholders, dest must have same ones
        if source_placeholders and source_placeholders != dest_placeholders:
            missing = source_placeholders - dest_placeholders
            extra = dest_placeholders - source_placeholders
            msg = f'Placeholder mismatch'
            if missing:
                msg += f'. Missing: {{{", ".join(missing)}}}'
            if extra:
                msg += f'. Extra: {{{", ".join(extra)}}}'
            self.errors.append(CSVValidationError(
                line_num,
                'FAIL_PLACEHOLDER',
                msg,
                row
            ))

    def _check_consistency(self, source: str, dest: str, context: str, line_num: int, row: Dict):
        """Check if same source_text+context always maps to same dest_text"""
        key = (normalize_translation_text(source), normalize_translation_text(context))
        dest_norm = normalize_translation_text(dest)

        if key in self.translation_map:
            existing = self.translation_map[key]
            if existing != dest_norm:
                self.errors.append(CSVValidationError(
                    line_num,
                    'FAIL_INCONSISTENT',
                    f'Inconsistent translation for "{source[:40]}": '
                    f'previously "{existing[:40]}", now "{dest[:40]}"',
                    row
                ))
        else:
            self.translation_map[key] = dest_norm

    def validate_multiple(self, csv_paths: List[str]) -> Dict:
        """
        Validate multiple CSV files
        Returns: {
            'all_valid': bool,
            'by_file': {csv_path: validation_result},
            'total_errors': int,
            'errors_by_type': {error_type: count}
        }
        """
        results_by_file = {}
        total_errors = 0
        errors_by_type = {}

        for csv_path in csv_paths:
            result = self.validate_file(csv_path)
            results_by_file[csv_path] = result
            total_errors += result['critical_count']

            for error in result['errors']:
                errors_by_type[error.error_type] = errors_by_type.get(error.error_type, 0) + 1

        all_valid = all(r['valid'] for r in results_by_file.values())

        return {
            'all_valid': all_valid,
            'by_file': results_by_file,
            'total_critical_errors': total_errors,
            'errors_by_type': errors_by_type
        }


def format_validation_report(validation_result: Dict, csv_path: str = None) -> str:
    """Format validation result as readable report"""
    lines = []

    if csv_path:
        lines.append(f"\nCSV: {Path(csv_path).name}")
        lines.append("=" * 80)

    result = validation_result if 'valid' in validation_result else validation_result.get('by_file', {}).get(csv_path)

    if not result:
        return "No validation results"

    errors = result.get('errors', [])
    critical = result.get('critical_count', 0)
    warning = result.get('warning_count', 0)

    if not errors:
        lines.append("[OK] No issues found")
        return "\n".join(lines)

    # Group by error type
    by_type = {}
    for error in errors:
        if error.error_type not in by_type:
            by_type[error.error_type] = []
        by_type[error.error_type].append(error)

    # Print critical errors first
    critical_types = {k: v for k, v in by_type.items() if k.startswith('FAIL')}
    warning_types = {k: v for k, v in by_type.items() if not k.startswith('FAIL')}

    if critical_types:
        lines.append(f"[FAIL] CRITICAL ERRORS: {critical}")
        for error_type, type_errors in critical_types.items():
            lines.append(f"  {error_type} ({len(type_errors)})")
            for error in type_errors[:3]:  # Show first 3
                lines.append(f"    - {error}")
            if len(type_errors) > 3:
                lines.append(f"    ... and {len(type_errors) - 3} more")

    if warning_types:
        lines.append(f"[WARN] WARNINGS: {warning}")
        for error_type, type_errors in warning_types.items():
            lines.append(f"  {error_type} ({len(type_errors)})")
            for error in type_errors[:2]:  # Show first 2
                lines.append(f"    - {error}")

    status = '[PASS]' if result['valid'] else '[FAIL]'
    lines.append(f"\nStatus: {status}")

    return "\n".join(lines)


def format_batch_report(validation_result: Dict) -> str:
    """Format validation report for multiple CSVs"""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("BATCH VALIDATION REPORT")
    lines.append("=" * 80)

    by_file = validation_result.get('by_file', {})
    all_valid = validation_result.get('all_valid', False)
    total_errors = validation_result.get('total_critical_errors', 0)

    # Summary
    passed = sum(1 for r in by_file.values() if r['valid'])
    failed = len(by_file) - passed

    lines.append(f"\nFiles: {passed} passed, {failed} failed")
    lines.append(f"Total critical errors: {total_errors}")

    if validation_result.get('errors_by_type'):
        lines.append("\nErrors by type:")
        for error_type, count in sorted(validation_result['errors_by_type'].items()):
            lines.append(f"  {error_type}: {count}")

    # Failed files
    if failed > 0:
        lines.append("\nFailed files:")
        for csv_path, result in sorted(by_file.items()):
            if not result['valid']:
                path = Path(csv_path).name
                lines.append(f"  [FAIL] {path} ({result['critical_count']} errors)")

    status_mark = "[PASS]" if all_valid else "[FAIL]"
    lines.append(f"\nOverall status: {status_mark}")
    lines.append("=" * 80)

    return "\n".join(lines)
