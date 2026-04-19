#!/usr/bin/env python3
"""
HTML Translation Quality Assurance
Validates generated HTML files for completeness and correctness
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from html.parser import HTMLParser


class HTMLQAError:
    """Represents a QA error found in HTML"""

    def __init__(self, error_type: str, message: str, line_num: int = None, element: str = None):
        self.error_type = error_type
        self.message = message
        self.line_num = line_num
        self.element = element

    def __repr__(self):
        if self.line_num:
            return f"[{self.error_type}] Line {self.line_num}: {self.message}"
        return f"[{self.error_type}] {self.message}"


class LinkExtractor(HTMLParser):
    """Extract all links from HTML"""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    self.links.append(value)


class HTMLValidator:
    """Validate generated HTML files for QA issues"""

    def __init__(self, translation_db=None):
        self.translation_db = translation_db
        self.errors: List[HTMLQAError] = []

    def validate_file(self, html_path: str, source_file: str = None, target_lang: str = None) -> Dict:
        """
        Validate a single generated HTML file
        Returns: {
            'valid': bool,
            'errors': List[HTMLQAError],
            'error_count': int,
            'warnings': List
        }
        """
        self.errors = []

        path = Path(html_path)
        if not path.exists():
            return {
                'valid': False,
                'errors': [HTMLQAError('FILE_NOT_FOUND', f'HTML file not found: {html_path}')],
                'error_count': 1,
                'warnings': []
            }

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self._check_metadata(content, target_lang)
            self._check_english_fallback(content, html_path, source_file, target_lang)
            self._check_broken_links(content)
            self._check_html_entities(content)

        except Exception as e:
            self.errors.append(HTMLQAError('READ_ERROR', f'Error reading HTML: {str(e)}'))

        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'error_count': len(self.errors),
            'warnings': []
        }

    def _check_metadata(self, content: str, target_lang: str = None):
        """Check HTML metadata (lang attribute, charset)"""
        # Check lang attribute
        if target_lang:
            lang_match = re.search(r'<html[^>]*lang=(["\'])([^"\']+)\1', content)
            if lang_match:
                current_lang = lang_match.group(2)
                if current_lang != target_lang and current_lang == 'en':
                    self.errors.append(HTMLQAError(
                        'FAIL_WRONG_LANG',
                        f'Wrong lang attribute: "en" should be "{target_lang}"'
                    ))

        # Check charset
        if 'charset=utf-8' not in content.lower():
            self.errors.append(HTMLQAError(
                'WARN_NO_CHARSET',
                'Missing or incorrect charset declaration'
            ))

    def _check_english_fallback(
        self,
        content: str,
        html_path: str,
        source_file: str = None,
        target_lang: str = None
    ):
        """
        Detect English text in generated file (indicates untranslated fallback)
        This is complex: need to compare against translation DB to know what SHOULD be translated
        """
        if not source_file or not target_lang or not self.translation_db:
            return

        # Extract text content from HTML (rough extraction)
        # Remove script/style content
        content_cleaned = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
        content_cleaned = re.sub(r'<style[^>]*>.*?</style>', '', content_cleaned, flags=re.DOTALL)

        # Remove HTML tags but keep text
        text_content = re.sub(r'<[^>]+>', ' ', content_cleaned)
        # Normalize whitespace
        text_content = re.sub(r'\s+', ' ', text_content).strip()

        # Try to fetch expected translations from DB
        try:
            # This is a placeholder - actual implementation depends on translate_manager
            # Check if DB has translations for this file/language
            if hasattr(self.translation_db, 'get_translations_for_file'):
                expected_translations = self.translation_db.get_translations_for_file(source_file, target_lang)
                # Look for English text that should have been translated
                for source_text, expected_target in expected_translations.items():
                    if source_text in text_content and expected_target not in text_content:
                        self.errors.append(HTMLQAError(
                            'FAIL_ENGLISH_FALLBACK',
                            f'English text found: "{source_text[:60]}" (should be "{expected_target[:60]}")'
                        ))
        except Exception:
            pass  # Skip if DB access fails

    def _check_broken_links(self, content: str):
        """Check for broken internal links"""
        extractor = LinkExtractor()
        try:
            extractor.feed(content)
        except Exception:
            return

        issues = []
        for link in extractor.links:
            # Check for common issues
            if '\\' in link:
                issues.append(('FAIL_BACKSLASH', f'Link contains backslash: {link}'))

            if link.startswith('../'):
                # Relative links are OK, but check they're not pointing to wrong lang
                if '/en/' in link or link.startswith('en/'):
                    issues.append(('FAIL_WRONG_LANG_LINK', f'Link points to English: {link}'))

            # Check for orphaned slashes
            if '//' in link and not link.startswith('http'):
                issues.append(('FAIL_DOUBLE_SLASH', f'Link has double slash: {link}'))

        for error_type, msg in issues:
            self.errors.append(HTMLQAError(error_type, msg))

    def _check_html_entities(self, content: str):
        """Check for broken HTML entities"""
        # Look for common entity issues
        issues = []

        # Orphaned ampersand (not followed by valid entity pattern)
        orphaned = re.findall(r'&(?![a-zA-Z0-9#]+;)', content)
        if orphaned:
            issues.append(('WARN_BROKEN_ENTITY', f'Found {len(orphaned)} incomplete entities'))

        # Check for double-encoded entities like "&amp;nbsp;"
        double_encoded = re.findall(r'&amp;[a-zA-Z0-9]+;', content)
        if double_encoded:
            issues.append(('FAIL_DOUBLE_ENCODED', f'Found {len(double_encoded)} double-encoded entities'))

        # Check for space-separated entity like "& nbsp;"
        spaced = re.findall(r'&\s+\w+;', content)
        if spaced:
            issues.append(('FAIL_SPACED_ENTITY', f'Found {len(spaced)} entities with spaces'))

        for error_type, msg in issues:
            self.errors.append(HTMLQAError(error_type, msg))

    def validate_multiple(self, html_paths: List[str]) -> Dict:
        """
        Validate multiple HTML files
        Returns summary of all validations
        """
        results_by_file = {}
        total_errors = 0
        errors_by_type = {}

        for html_path in html_paths:
            result = self.validate_file(html_path)
            results_by_file[html_path] = result
            total_errors += result['error_count']

            for error in result['errors']:
                errors_by_type[error.error_type] = errors_by_type.get(error.error_type, 0) + 1

        all_valid = all(r['valid'] for r in results_by_file.values())

        return {
            'all_valid': all_valid,
            'by_file': results_by_file,
            'total_errors': total_errors,
            'errors_by_type': errors_by_type
        }


def format_html_validation_report(validation_result: Dict, html_path: str = None) -> str:
    """Format HTML validation result as readable report"""
    lines = []

    if html_path:
        lines.append(f"\nHTML: {Path(html_path).name}")
        lines.append("=" * 80)

    result = validation_result if 'valid' in validation_result else validation_result.get('by_file', {}).get(html_path)

    if not result:
        return "No validation results"

    errors = result.get('errors', [])

    if not errors:
        lines.append("[OK] All checks passed")
        return "\n".join(lines)

    # Group by error type
    by_type = {}
    for error in errors:
        if error.error_type not in by_type:
            by_type[error.error_type] = []
        by_type[error.error_type].append(error)

    # Print critical errors first
    critical_types = {k: v for k, v in by_type.items() if k.startswith('FAIL')}
    warning_types = {k: v for k, v in by_type.items() if k.startswith('WARN')}

    if critical_types:
        lines.append(f"[FAIL] CRITICAL ERRORS: {sum(len(v) for v in critical_types.values())}")
        for error_type, type_errors in critical_types.items():
            lines.append(f"  {error_type} ({len(type_errors)})")
            for error in type_errors[:2]:  # Show first 2
                lines.append(f"    - {error.message}")

    if warning_types:
        lines.append(f"[WARN] WARNINGS: {sum(len(v) for v in warning_types.values())}")
        for error_type, type_errors in warning_types.items():
            lines.append(f"  {error_type} ({len(type_errors)})")
            for error in type_errors[:1]:  # Show first 1
                lines.append(f"    - {error.message}")

    status = '[PASS]' if result['valid'] else '[FAIL]'
    lines.append(f"\nStatus: {status}")

    return "\n".join(lines)


def format_html_batch_report(validation_result: Dict) -> str:
    """Format validation report for multiple HTML files"""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("HTML VALIDATION REPORT")
    lines.append("=" * 80)

    by_file = validation_result.get('by_file', {})
    all_valid = validation_result.get('all_valid', False)
    total_errors = validation_result.get('total_errors', 0)

    # Summary
    passed = sum(1 for r in by_file.values() if r['valid'])
    failed = len(by_file) - passed

    lines.append(f"\nFiles: {passed} passed, {failed} failed")
    lines.append(f"Total errors: {total_errors}")

    if validation_result.get('errors_by_type'):
        lines.append("\nErrors by type:")
        for error_type, count in sorted(validation_result['errors_by_type'].items()):
            prefix = "[FAIL]" if error_type.startswith('FAIL') else "[WARN]"
            lines.append(f"  {prefix} {error_type}: {count}")

    # Failed files
    if failed > 0:
        lines.append("\nFailed files:")
        for html_path, result in sorted(by_file.items()):
            if not result['valid']:
                path = Path(html_path).name
                lines.append(f"  [FAIL] {path} ({result['error_count']} errors)")

    status = '[PASS]' if all_valid else '[FAIL]'
    lines.append(f"\nOverall status: {status}")
    lines.append("=" * 80)

    return "\n".join(lines)
