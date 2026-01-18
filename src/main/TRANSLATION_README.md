# Translation System

A Python-based system for managing multilingual HTML translations with translation memory and path mappings.

## Quick Start

```bash
# 1. Setup path mappings
python batch_translate.py setup
# Edit path_mappings.csv

# 2. Import path mappings
python batch_translate.py import-paths

# 3. Extract missing translations
python batch_translate.py extract

# 4. Translate CSV files in translations_pending/

# 5. Import completed translations
python batch_translate.py import

# 6. View progress
python batch_translate.py overview
```

## Core Features

- **Translation Memory**: Reuse translations across pages (translate once, use everywhere)
- **Path Mappings**: Consistent URL translations (en/travel → de/reisen)
- **Change Detection**: Only extract new/modified content
- **Progress Dashboard**: HTML overview showing translation status
- **No Dependencies**: Pure Python standard library

## Commands

```bash
python batch_translate.py setup           # Create path mapping template
python batch_translate.py import-paths    # Import path mappings from CSV
python batch_translate.py extract         # Extract all missing translations
python batch_translate.py extract-file FILE  # Extract one file
python batch_translate.py import          # Import completed translation CSVs
python batch_translate.py overview        # Generate HTML progress dashboard
python batch_translate.py stats           # Show translation statistics
python batch_translate.py export          # Backup database to JSON
python batch_translate.py clean           # Delete pending CSVs
```

## Configuration

Edit `batch_translate.py` to configure:

```python
SOURCE_LANG = "en"
TARGET_LANGS = ["fr", "de", "pt", "nl", "es", "it", "ml", "pa", "hi"]
SOURCE_DIR = "en/photography"  # or "en" for all
```

## Workflow

1. **Define Path Mappings** (`path_mappings.csv`):
   ```csv
   source_lang,target_lang,source_path,target_path
   en,de,en/photography,de/fotografie
   en,fr,en/travel,fr/voyages
   ```

2. **Extract Translations**: System finds missing translations and exports to CSV

3. **Translate Manually**: Fill in `dest_text` column in CSV files

4. **Import**: System stores translations in SQLite database

5. **Monitor Progress**: View `translation_overview.html` in browser

## File Structure

```
├── translate_manager.py        # Core translation engine
├── batch_translate.py          # Batch processing CLI
├── html_generator.py           # HTML file generation
├── check_db.py                 # Database inspection tool
│
├── translations.db             # SQLite database (auto-created)
├── path_mappings.csv           # Path translations (manual)
├── translation_overview.html   # Progress dashboard (generated)
│
└── translations_pending/       # CSV files for translation
    ├── missing_*.csv           # Pending translations
    └── completed/              # Imported CSVs
```

## Translation Memory Example

First page:
```csv
en,de,Photography,Fotografie
en,de,John Samuel,John Samuel
```

Second page:
- "Photography" and "John Samuel" NOT in CSV (already translated)
- Only NEW text appears

Result: Translate 1,500 unique phrases instead of 5,000 total!

## Path Mapping Benefits

Define once:
```csv
en,de,en/photography/cities/France/Paris.html,de/reisen/städte/Frankreich/Paris.html
```

Use forever - no more guessing paths!

## HTML Generation

After translating, generate target HTML files:

```bash
# Generate single file
python html_generator.py translate-file --source-file en/file.html --target-lang de

# Generate all files in directory
python html_generator.py translate-dir --source-dir en/photography --target-lang de

# Dry-run mode (preview without writing)
python html_generator.py translate-dir --source-dir en/photography --target-lang fr --dry-run

# No confirmation (skip prompts for existing files)
python html_generator.py translate-dir --source-dir en/photography --target-lang de --no-confirm
```

This creates translated HTML files with:
- Translated text content
- Rewritten internal links using path mappings
- Same structure as source

### Overwrite Protection

**By default**, the generator asks for confirmation before overwriting existing files:
```
File exists: fr/photographie/Stockholm.html
Overwrite? [y/N/a/q] (y=yes, N=no, a=all, q=quit):
```

Options:
- `y` - Yes, overwrite this file
- `N` - No, skip this file (default)
- `a` - All, overwrite all remaining files without asking
- `q` - Quit, cancel generation

Use `--no-confirm` to skip all prompts and overwrite automatically.

Use `--dry-run` to preview what would be generated without making changes.

## Database Schema

```sql
-- Translations
translations (source_lang, target_lang, source_text, target_text, context)

-- Path mappings
path_mappings (source_lang, target_lang, source_path, target_path)

-- File tracking
file_tracking (file_path, language, content_hash, last_modified)
```

## Requirements

- Python 3.6+
- No external dependencies!

## Tips

1. **Start with Common Content**: Translate navigation/footer first for maximum reuse
2. **One Language at a Time**: Complete one language fully before starting another
3. **Regular Backups**: `python batch_translate.py export` to create JSON backups
4. **Check Progress**: Generate overview after each import session

## Context-Aware Translation

Same word, different contexts = separate translations:

```csv
en,pt,Home,Início,nav/a,text       # Navigation
en,pt,Home,Casa,article/h1,text    # Article heading
```

## Troubleshooting

**"No missing translations"**: File already translated or has no translatable content

**"Import failed"**: Check CSV format and UTF-8 encoding

**"Path mapping conflict"**: Check for duplicate mappings in database

## License

Provided as-is for multilingual website translation needs.
