#!/usr/bin/env python3
"""
HTML File Generator
Generates translated HTML files from the translation database
"""

import os
import re
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, List, Optional
from translate_manager import TranslationDatabase


class HTMLTranslator(HTMLParser):
    """Translate HTML content using the translation database"""

    # Tags that should not be translated
    SKIP_TAGS = {'script', 'style', 'code', 'pre'}

    # Attributes to translate
    TRANSLATABLE_ATTRS = {
        'title', 'alt', 'placeholder', 'aria-label',
        'aria-description', 'content'
    }

    def __init__(self, db: TranslationDatabase, source_lang: str, target_lang: str):
        super().__init__()
        self.db = db
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.output = []
        self.current_tag_stack = []
        self.skip_content = False

    def handle_starttag(self, tag, attrs):
        self.current_tag_stack.append(tag)

        # Check if we should skip this tag's content
        if tag in self.SKIP_TAGS:
            self.skip_content = True

        # Check for no-translate class
        for attr, value in attrs:
            if attr == 'class' and value and 'no-translate' in value.split():
                self.skip_content = True

        # Translate attributes and build tag
        translated_attrs = []
        for attr, value in attrs:
            if attr in self.TRANSLATABLE_ATTRS and value and value.strip():
                context = f'{tag}[@{attr}]'

                # Special handling for meta content
                if tag == 'meta' and attr == 'content':
                    meta_name = dict(attrs).get('name', '')
                    if meta_name in ['description', 'keywords']:
                        translation = self.db.get_translation(
                            self.source_lang, self.target_lang,
                            value.strip(), context
                        )
                        if translation:
                            value = translation

                else:
                    translation = self.db.get_translation(
                        self.source_lang, self.target_lang,
                        value.strip(), context
                    )
                    if translation:
                        value = translation

            translated_attrs.append((attr, value))

        # Build the opening tag
        attrs_str = ''.join([f' {attr}="{value}"' for attr, value in translated_attrs])
        self.output.append(f'<{tag}{attrs_str}>')

    def handle_endtag(self, tag):
        if self.current_tag_stack and self.current_tag_stack[-1] == tag:
            self.current_tag_stack.pop()

        if tag in self.SKIP_TAGS:
            self.skip_content = False

        self.output.append(f'</{tag}>')

    def handle_startendtag(self, tag, attrs):
        # Self-closing tags like <img />
        translated_attrs = []
        for attr, value in attrs:
            if attr in self.TRANSLATABLE_ATTRS and value and value.strip():
                context = f'{tag}[@{attr}]'
                translation = self.db.get_translation(
                    self.source_lang, self.target_lang,
                    value.strip(), context
                )
                if translation:
                    value = translation

            translated_attrs.append((attr, value))

        attrs_str = ''.join([f' {attr}="{value}"' for attr, value in translated_attrs])
        self.output.append(f'<{tag}{attrs_str} />')

    def handle_data(self, data):
        if self.skip_content:
            self.output.append(data)
            return

        # For whitespace-only content, keep as is
        if not data.strip():
            self.output.append(data)
            return

        # Get current context
        context = '/'.join(self.current_tag_stack) if self.current_tag_stack else 'text'

        # Try to get translation
        translation = self.db.get_translation(
            self.source_lang, self.target_lang,
            data.strip(), context
        )

        if translation:
            # Preserve leading/trailing whitespace
            leading_space = data[:len(data) - len(data.lstrip())]
            trailing_space = data[len(data.rstrip()):]
            self.output.append(f'{leading_space}{translation}{trailing_space}')
        else:
            # No translation found, keep original
            self.output.append(data)

    def handle_comment(self, data):
        """Preserve HTML comments"""
        self.output.append(f'<!--{data}-->')

    def handle_decl(self, decl):
        """Preserve DOCTYPE declarations"""
        self.output.append(f'<!{decl}>')

    def get_translated_html(self) -> str:
        """Get the translated HTML"""
        return ''.join(self.output)


class LinkRewriter:
    """Rewrite internal links based on path mappings"""

    def __init__(self, db: TranslationDatabase, source_lang: str, target_lang: str):
        self.db = db
        self.source_lang = source_lang
        self.target_lang = target_lang

    def rewrite_links(self, html: str, current_file_path: str) -> str:
        """
        Rewrite internal links in HTML based on path mappings

        Args:
            html: HTML content
            current_file_path: Current file path (e.g., 'en/photography/Sweden/Stockholm.html')

        Returns:
            HTML with rewritten links
        """
        # Pattern to match href attributes
        href_pattern = r'href=["\']([^"\']+)["\']'

        def replace_href(match):
            original_href = match.group(1)

            # Skip external links, anchors, and non-HTML links
            if (original_href.startswith(('http://', 'https://', 'mailto:', 'tel:', '#')) or
                original_href.startswith('javascript:')):
                return match.group(0)

            # Resolve relative path to absolute and normalize
            current_dir = Path(current_file_path).parent

            # Combine and normalize the path (resolves .. and .)
            try:
                # For relative paths, we need to normalize without resolving to filesystem
                combined = current_dir / original_href
                # Normalize the path parts to resolve .. and .
                parts = []
                for part in combined.parts:
                    if part == '..':
                        if parts:
                            parts.pop()
                    elif part != '.':
                        parts.append(part)
                resolved_path = str(Path(*parts)) if parts else ''
                resolved_path = resolved_path.replace('\\', '/')
            except (ValueError, IndexError):
                # If path resolution fails, return original
                return match.group(0)

            # Try to find path mapping
            # Check if there's a specific file mapping
            target_path = self.db.get_path_mapping(
                self.source_lang, self.target_lang, resolved_path
            )

            if not target_path:
                # Try directory mapping
                for i in range(len(Path(resolved_path).parts), 0, -1):
                    partial_path = str(Path(*Path(resolved_path).parts[:i]))
                    dir_mapping = self.db.get_path_mapping(
                        self.source_lang, self.target_lang, partial_path
                    )
                    if dir_mapping:
                        # Replace the mapped part
                        remaining = str(Path(*Path(resolved_path).parts[i:]))
                        if remaining:
                            target_path = str(Path(dir_mapping) / remaining)
                        else:
                            target_path = dir_mapping
                        break

            if target_path:
                # Calculate relative path from current translated file
                # First, find where the current source file will be translated to
                current_file_normalized = current_file_path.replace('\\', '/')

                # Try exact file mapping first
                current_file_target = self.db.get_path_mapping(
                    self.source_lang, self.target_lang, current_file_normalized
                )

                if not current_file_target:
                    # Try directory mapping
                    current_dir_parts = Path(current_file_path).parts
                    for i in range(len(current_dir_parts) - 1, 0, -1):  # Don't include filename
                        partial = str(Path(*current_dir_parts[:i])).replace('\\', '/')
                        dir_mapping = self.db.get_path_mapping(
                            self.source_lang, self.target_lang, partial
                        )
                        if dir_mapping:
                            # Construct target path for current file
                            remaining = current_dir_parts[i:]
                            current_file_target = str(Path(dir_mapping) / Path(*remaining)).replace('\\', '/')
                            break

                if current_file_target:
                    # Get directory of target file
                    current_target_dir = str(Path(current_file_target).parent).replace('\\', '/')

                    # Calculate relative path
                    try:
                        relative = os.path.relpath(target_path, current_target_dir)
                        # Normalize path separators for consistency
                        relative = relative.replace('\\', '/')
                        return f'href="{relative}"'
                    except ValueError:
                        # Can't create relative path (different drives on Windows)
                        return match.group(0)

            # If no mapping found or couldn't rewrite, keep original
            return match.group(0)

        return re.sub(href_pattern, replace_href, html)


class HTMLGenerator:
    """Generate translated HTML files"""

    def __init__(self, source_lang: str = 'en', db_path: str = 'translations.db'):
        self.source_lang = source_lang
        self.db = TranslationDatabase(db_path)

    def translate_file(self, source_file: str, target_lang: str,
                      output_file: str = None, rewrite_links: bool = True,
                      require_mapping: bool = True, dry_run: bool = False,
                      confirm: bool = True) -> str:
        """
        Translate an HTML file

        Args:
            source_file: Source HTML file path
            target_lang: Target language code
            output_file: Output file path (if None, uses path mapping)
            rewrite_links: Whether to rewrite internal links
            require_mapping: If True, only generate if path mapping exists
            dry_run: If True, only show what would be generated without writing files
            confirm: If True, ask for confirmation before overwriting existing files

        Returns:
            Path to generated file or None if no mapping exists

        Raises:
            ValueError: If require_mapping=True and no mapping exists
        """
        # Read source file
        with open(source_file, 'r', encoding='utf-8') as f:
            source_html = f.read()

        # Translate HTML
        translator = HTMLTranslator(self.db, self.source_lang, target_lang)
        translator.feed(source_html)
        translated_html = translator.get_translated_html()

        # Rewrite links if requested
        if rewrite_links:
            link_rewriter = LinkRewriter(self.db, self.source_lang, target_lang)
            translated_html = link_rewriter.rewrite_links(translated_html, source_file)

        # Determine output file path
        if output_file is None:
            # Normalize source path
            source_path = str(Path(source_file)).replace('\\', '/')

            # Try exact file mapping first
            target_path = self.db.get_path_mapping(
                self.source_lang, target_lang, source_path
            )

            if not target_path:
                # Try directory mapping + filename
                source_dir = str(Path(source_file).parent).replace('\\', '/')
                source_filename = Path(source_file).name

                target_dir = self.db.get_path_mapping(
                    self.source_lang, target_lang, source_dir
                )

                if target_dir:
                    target_path = str(Path(target_dir) / source_filename).replace('\\', '/')

            if not target_path and require_mapping:
                raise ValueError(
                    f"No path mapping found for {source_path} -> {target_lang}. "
                    f"Add mapping to path_mappings.csv and run 'import-paths'."
                )

            if not target_path:
                # Fallback: auto-generate (only if require_mapping=False)
                parts = list(Path(source_file).parts)
                if parts[0] == self.source_lang:
                    parts[0] = target_lang
                target_path = str(Path(*parts)).replace('\\', '/')

            output_file = target_path

        # Check if file exists and handle confirmation
        file_exists = Path(output_file).exists()

        if dry_run:
            # Dry run mode: just report what would be done
            if file_exists:
                print(f"[DRY-RUN] Would overwrite: {output_file}")
            else:
                print(f"[DRY-RUN] Would create: {output_file}")
            return output_file

        # Confirmation mode: ask before overwriting
        if file_exists and confirm:
            response = input(f"File exists: {output_file}\nOverwrite? [y/N/a/q] (y=yes, N=no, a=all, q=quit): ").strip().lower()

            if response == 'q':
                raise KeyboardInterrupt("Generation cancelled by user")
            elif response == 'a':
                # "All" means skip confirmation for remaining files
                # This is handled by the caller setting confirm=False
                pass
            elif response != 'y':
                print(f"Skipped: {output_file}")
                return None

        # Create output directory
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Write translated file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_html)

        return output_file

    def translate_directory(self, source_dir: str, target_lang: str,
                          pattern: str = '**/*.html',
                          rewrite_links: bool = True,
                          skip_unmapped: bool = True,
                          dry_run: bool = False,
                          confirm: bool = True) -> List[str]:
        """
        Translate all HTML files in a directory

        Args:
            source_dir: Source directory
            target_lang: Target language code
            pattern: Glob pattern for files
            rewrite_links: Whether to rewrite internal links
            skip_unmapped: If True, skip files without path mappings
            dry_run: If True, only show what would be generated without writing files
            confirm: If True, ask for confirmation before overwriting existing files

        Returns:
            List of generated file paths
        """
        source_path = Path(source_dir)
        generated_files = []
        skipped_files = []
        skip_all_confirmation = False

        for source_file in source_path.glob(pattern):
            if source_file.is_file():
                try:
                    # Handle "all" response from previous confirmation
                    current_confirm = confirm and not skip_all_confirmation

                    output_file = self.translate_file(
                        str(source_file), target_lang,
                        rewrite_links=rewrite_links,
                        require_mapping=skip_unmapped,
                        dry_run=dry_run,
                        confirm=current_confirm
                    )

                    if output_file:
                        generated_files.append(output_file)
                        if not dry_run:
                            print(f"Generated: {output_file}")

                except ValueError as e:
                    # No mapping exists
                    if skip_unmapped:
                        skipped_files.append(str(source_file))
                        if not dry_run:
                            print(f"Skipped (no mapping): {source_file}")
                    else:
                        raise
                except KeyboardInterrupt:
                    print("\nGeneration cancelled by user")
                    break
                except Exception as e:
                    print(f"Failed: {source_file} - {str(e)}")

        if skipped_files:
            print(f"\nSkipped {len(skipped_files)} files without path mappings.")
            print("Add mappings to path_mappings.csv for these files:")
            for f in skipped_files[:5]:  # Show first 5
                print(f"  - {f}")
            if len(skipped_files) > 5:
                print(f"  ... and {len(skipped_files) - 5} more")

        return generated_files

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate translated HTML files from translation database'
    )

    parser.add_argument('command', choices=['translate-file', 'translate-dir'])

    parser.add_argument('--source-file',
                       help='Source HTML file (for translate-file)')

    parser.add_argument('--source-dir',
                       help='Source directory (for translate-dir)')

    parser.add_argument('--target-lang', required=True,
                       help='Target language code')

    parser.add_argument('--output',
                       help='Output file/directory (auto-generated if not specified)')

    parser.add_argument('--no-rewrite-links', action='store_true',
                       help='Do not rewrite internal links')

    parser.add_argument('--pattern', default='**/*.html',
                       help='File pattern for translate-dir (default: **/*.html)')

    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be generated without writing files')

    parser.add_argument('--no-confirm', action='store_true',
                       help='Do not ask for confirmation before overwriting files')

    args = parser.parse_args()

    generator = HTMLGenerator()

    try:
        if args.command == 'translate-file':
            if not args.source_file:
                print("Error: --source-file required for translate-file")
                return 1

            output_file = generator.translate_file(
                args.source_file,
                args.target_lang,
                args.output,
                rewrite_links=not args.no_rewrite_links,
                dry_run=args.dry_run,
                confirm=not args.no_confirm
            )

            if output_file and not args.dry_run:
                print(f"Generated: {output_file}")

        elif args.command == 'translate-dir':
            if not args.source_dir:
                print("Error: --source-dir required for translate-dir")
                return 1

            if args.dry_run:
                print("[DRY-RUN MODE] Showing what would be generated:\n")

            generated_files = generator.translate_directory(
                args.source_dir,
                args.target_lang,
                args.pattern,
                rewrite_links=not args.no_rewrite_links,
                dry_run=args.dry_run,
                confirm=not args.no_confirm
            )

            if args.dry_run:
                print(f"\n[DRY-RUN] Would generate {len(generated_files)} files")
            else:
                print(f"\nGenerated {len(generated_files)} files")

    finally:
        generator.close()

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
