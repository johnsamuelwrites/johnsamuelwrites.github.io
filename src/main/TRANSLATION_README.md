# Translation System

A Python-based system for managing multilingual HTML translations with explicit workflow state tracking, QA gates, and translation memory.

## Quick Start (Recommended)

Run the complete workflow with one command:

```bash
# Start web dashboard in separate terminal
python batch_translate.py serve --port 8000
# Opens: http://localhost:8000

# Run full pipeline (sync → validate → import → generate → validate → glossary)
python batch_translate.py pipeline --target-langs es pt
# Answer prompts:
# - Review CSVs in web dashboard (http://localhost:8000)
# - Answer "Import now?" prompt when ready
# - Pipeline generates HTML and exports glossaries automatically
```

## Traditional Step-by-Step Workflow

For granular control:

```bash
# 1. Extract changed files (parallel, with change detection)
python batch_translate.py sync --source-dir en/travel --target-langs es pt

# 2. Review & edit in web dashboard (no CSV tool needed)
python batch_translate.py serve --port 8000

# 3. Validate translations before import (QA gates)
python batch_translate.py validate-csv

# 4. Import validated translations
python batch_translate.py import

# 5. Generate translated files
python batch_translate.py generate --source-dir en/travel --target-langs es pt --require-complete

# 6. Validate generated HTML files
python batch_translate.py validate-html --target-langs es pt

# 7. Export glossaries for next cycle
python batch_translate.py glossary-sync --target-langs es pt
```

## Core Features

**State & QA:**
- **Explicit State Tracking**: SQLite database tracks workflow (PENDING_EXTRACT → PENDING_REVIEW → IMPORTED → GENERATION_COMPLETE)
- **Change Detection**: SHA256-based file hashing, only extract changed content
- **Parallel Extraction**: ThreadPoolExecutor with 4 workers (configurable)
- **Pre-Import QA Gates**: Validate translations before importing (empty cells, unchanged English, placeholders, consistency)
- **Post-Generation QA**: Validate HTML files for English fallback, broken links, entity corruption
- **Web Dashboard**: Flask-based inline CSV editor with auto-save (no external tools)

**Pipeline & Automation:**
- **Pipeline Orchestration**: Single command runs complete workflow with progress reporting
- **Glossary Auto-Export**: Extract high-frequency translations for reuse (top 200 entries, min 2x usage)
- **Interactive Import Prompts**: Decide when to import with full visibility into extraction results

**Core Concepts:**
- **Translation Memory**: Reuse translations across pages (translate once, use everywhere)
- **Path Mappings**: Consistent URL translations (en/travel → es/viajes)
- **No External Dependencies**: Pure Python (Flask for dashboard only, optional)

## Commands

**Pipeline (Recommended):**
```bash
python batch_translate.py pipeline --target-langs es pt [--auto-import] [--skip-generation] [--force]
python batch_translate.py serve --port 8000                          # Web dashboard for CSV review
python batch_translate.py glossary-sync --target-langs es pt         # Export glossaries
```

**Step-by-Step:**
```bash
python batch_translate.py sync --source-dir en/travel --target-langs es pt    # Extract changed files
python batch_translate.py validate-csv                               # Pre-import validation
python batch_translate.py import                                     # Import validated CSVs
python batch_translate.py generate --target-langs es --require-complete       # Generate HTML
python batch_translate.py validate-html --target-langs es            # Post-generation validation
python batch_translate.py status                                     # View workflow state
```

**Legacy:**
```bash
python batch_translate.py setup           # Create path mapping template
python batch_translate.py import-paths    # Import path mappings from CSV
python batch_translate.py extract         # Extract all missing translations
python batch_translate.py prefill         # Prefill from DB + glossary
python batch_translate.py completeness    # Show per-file translation progress
python batch_translate.py overview        # HTML progress dashboard
python batch_translate.py stats           # Translation statistics
python batch_translate.py export          # Backup database to JSON
python batch_translate.py clean           # Delete pending CSVs
```

## Configuration

Databases (auto-created):
```
../photography/translations.db       # Translation memory
../photography/translations_state.db # Workflow state
```

Optional: Edit `translation_config.py` to configure:
```python
SOURCE_LANG = "en"
TARGET_LANGS = ["es", "pt"]
SOURCE_DIR = "en/photography"  # or "en" for all
DB_PATH = "../photography/translations.db"
STATE_DB_PATH = "../photography/translations_state.db"
GLOSSARY_DIR = "../photography"
```

Pipeline Options:
```bash
--target-langs es pt    # Languages to process
--auto-import           # Skip "Import now?" prompt, auto-import if valid
--skip-generation       # Stop after import, don't generate HTML
--force                 # Force re-extract all files (ignore change detection)
```

## Workflow (Pipeline)

### Full Pipeline (Recommended)

```bash
# Terminal 1: Start web dashboard
python batch_translate.py serve --port 8000

# Terminal 2: Run pipeline
python batch_translate.py pipeline --target-langs es pt
```

Pipeline Steps:
1. **Sync** - Extract changed files using parallel processing with change detection
2. **Validate CSV** - Pre-import QA: check for empty cells, unchanged English, placeholders, inconsistencies
3. **Import Prompt** - Decision point: "Import now? (yes/no):" 
   - If yes: Proceed to generation
   - If no: Return and review in web dashboard
4. **Generate** - Regenerate affected HTML files
5. **Validate HTML** - Post-generation QA: check for English fallback, broken links
6. **Glossary Export** - Extract high-frequency translations for reuse in next cycle

Output: Detailed pipeline report with all metrics

### Step-by-Step Workflow (for Granular Control)

1. **Extract Changed Files**:
   ```bash
   python batch_translate.py sync --source-dir en/travel --target-langs es pt --force
   ```
   Output: CSVs in `translations_pending/`

2. **Review in Web Dashboard**:
   ```bash
   python batch_translate.py serve --port 8000
   # Edit translations inline with auto-save
   # View glossary references
   # Check status
   ```

3. **Validate Before Import**:
   ```bash
   python batch_translate.py validate-csv
   # Shows validation report with pass/fail status
   ```

4. **Import**:
   ```bash
   python batch_translate.py import
   # Stores validated translations in database
   ```

5. **Generate**:
   ```bash
   python batch_translate.py generate --target-langs es pt --require-complete
   # Generates only files with 100% translations
   ```

6. **Validate Output**:
   ```bash
   python batch_translate.py validate-html --target-langs es pt
   # Checks for English fallback, broken links
   ```

7. **Export Glossaries**:
   ```bash
   python batch_translate.py glossary-sync --target-langs es pt
   # Exports top 200 high-frequency translations for reuse
   ```

## Web Dashboard

Lightweight Flask-based CSV editor replacing manual Excel editing:

```bash
python batch_translate.py serve --port 8000
# Opens: http://localhost:8000
```

Features:
- **CSV Review Tab**: List pending files sorted by completion %
  - Click to open inline editor
  - Edit translations directly in browser
  - Auto-saves on change (no "Save" button needed)
  - Shows missing (◯) vs completed (✓)

- **Glossary Tab**: Browse existing translations
  - Reference material while filling CSVs
  - Language-specific entries
  - Learn translation patterns

- **Status Tab**: Quick workflow health check
  - Batch stages (pending/imported/generated)
  - Generated file QA status

Keyboard shortcuts:
- Tab: Move to next field
- Enter: Save and move down
- Ctrl+S: Save all

## Quality Assurance

### Pre-Import QA Gates

Automatically validate translations before importing:

```bash
python batch_translate.py validate-csv
```

Checks:
- **FAIL_EMPTY_DEST**: Empty destination text cells
- **FAIL_UNCHANGED_EN**: Destination identical to source (incomplete translations)
- **FAIL_PLACEHOLDER**: Broken {placeholder} syntax
- **FAIL_INCONSISTENT**: Same source+context with different translations

Output: Detailed report with line numbers, allowing batch review before import

### Post-Generation QA Gates

Validate generated HTML files:

```bash
python batch_translate.py validate-html --target-langs es
```

Checks:
- **FAIL_ENGLISH_FALLBACK**: English text in generated file (indicates missing translation)
- **FAIL_BROKEN_LINKS**: Path mapping issues (href doesn't match path_mappings)
- **FAIL_ENTITY_ISSUES**: HTML entity corruption (&amp; etc.)
- **FAIL_WRONG_LANG**: lang attribute mismatch

### Safe Generation with --require-complete

```bash
# ✓ Safe: Generate ONLY files with 100% translations
python batch_translate.py generate --target-langs es --require-complete

# ✗ Unsafe: Generate all files (includes English fallback for missing translations)
python batch_translate.py generate --target-langs es
```

With `--require-complete`:
- Files with 100% translations are generated
- Files with any missing translations are skipped with a warning
- No incomplete files are ever written
- QA validation catches remaining issues before output

## Workflow State Tracking

View current translation state:

```bash
python batch_translate.py status
```

Shows:
- **Batch Status**: PENDING_EXTRACT, PENDING_REVIEW, REVIEW_APPROVED, IMPORTED, GENERATION_COMPLETE
- **CSV Status**: PENDING, REVIEWED, APPROVED, IMPORTED
- **QA Status**: PENDING, PASS, FAIL_* (with specific error types)
- **Generated Files**: Count by QA status

State Database:
- Location: `../photography/translations_state.db`
- Tracks: Batch workflows, CSV files, generated files, source file hashes
- Purpose: Explicit state prevents workflow inference errors

## File Structure

```
src/main/
├── Pipeline & Automation
│   ├── pipeline_manager.py          # Orchestrates complete workflow
│   ├── glossary_manager.py          # Auto-extract high-frequency translations
│   ├── web_dashboard.py             # Flask web interface for CSV editing
│
├── State & QA
│   ├── sync_manager.py              # Parallel extraction with change detection
│   ├── state_manager.py             # Explicit workflow state tracking
│   ├── csv_validators.py            # Pre-import validation
│   ├── html_validators.py           # Post-generation validation
│
├── Core
│   ├── translate_manager.py         # Core translation engine
│   ├── batch_translate.py           # CLI dispatcher
│   ├── html_generator.py            # HTML generation
│
../photography/
├── translations.db                  # Translation memory 
├── translations_state.db            # Workflow state 
├── path_mappings.csv                # Path translations (manual)
├── translation_glossary_es.json     # Spanish glossary (auto-exported)
├── translation_glossary_pt.json     # Portuguese glossary (auto-exported)
│
└── translations_pending/            # CSV files for translation
    ├── missing_*.csv                # Pending translations
    └── completed/                   # Imported CSVs (backed up)
```

## Translation Memory and Glossaries

**Translation Memory**: Reused across all files
- First extraction: Translate all text
- Next extraction: Only new/changed text appears
- Result: Translate 1,500 unique phrases instead of 5,000 total!

**Glossaries**: Auto-exported high-frequency translations
- Extracted via `glossary-sync` command
- Top 200 entries, minimum 2x usage threshold
- JSON format for easy sharing and version control
- Pre-fills CSVs automatically in next cycle

Example glossary (Spanish):
```json
{
  "Home": "Inicio",
  "Photography": "Fotografía",
  "Travel": "Viajes",
  "About": "Acerca de"
}
```

## Parallel Processing

**Sync Command** uses ThreadPoolExecutor:
- 4 workers by default (configurable)
- Each worker extracts from independent source files
- Thread-local database connections (SQLite thread-safety)
- SHA256 change detection (only extract changed files)
- Fast parallel prefill from glossary

Example (152 files extracted in parallel):
```
Changed files: 3
es:
  Files extracted: 109
  Translations: 2,077
  Glossary prefilled: 847
```

## HTML Generation

Generate translated HTML files via pipeline or manually:

```bash
# Via pipeline (automatic, with validation)
python batch_translate.py pipeline --target-langs es pt

# Manual generation (standalone)
python batch_translate.py generate --target-langs es --require-complete

# Dry-run mode (preview without writing)
python batch_translate.py generate --target-langs es --require-complete --dry-run
```

Features:
- Rewritten internal links using path mappings
- 100% translation guarantee when using `--require-complete`
- Post-generation QA validation (catches errors)
- Overwrite protection (confirmation prompts by default)

### Generation Options

```bash
--require-complete      # Only generate files with 100% translations (RECOMMENDED)
--force                 # Skip confirmation prompts (safe with --require-complete)
--dry-run               # Preview without writing files
--source-dir PATH       # Source directory (default: en/photography)
```

## Database Schema

**Translation Memory (translations.db):**
```sql
translations (source_lang, target_lang, source_text, target_text, context)
path_mappings (source_lang, target_lang, source_path, target_path)
file_tracking (file_path, language, content_hash, last_modified)
```

**Workflow State (translations_state.db):**
```sql
batches (batch_id, source_lang, target_lang, status, created_at)
csv_files (batch_id, source_file, csv_path, status)
generated_files (source_file, target_lang, target_path, qa_status)
file_hashes (file_path, hash_value, updated_at)
```

## Requirements

- Python 3.6+
- Flask (for web dashboard, optional: `pip install flask`)
- No other external dependencies

## Tips

1. **Use Pipeline Command**: Simplest way to run complete workflow (`pipeline --target-langs es pt`)
2. **Always Use --require-complete**: Prevents incomplete files with English fallback
3. **Web Dashboard First**: Review in browser before import decision
4. **Check State Often**: Run `status` command to verify workflow progress
5. **Enable QA Validation**: Both CSV and HTML validators catch errors before output
6. **Glossary Management**: Auto-exported glossaries speed up next translation cycle
7. **One Language at a Time**: Complete one language fully before starting another
8. **Monitor with Dashboard**: Web interface provides real-time status and editing capability

## Context-Aware Translation

Same word, different contexts = separate translations. The system tracks these automatically:

```csv
en,pt,Home,Início,nav/a,text       # Navigation link
en,pt,Home,Casa,article/h1,text    # Article heading
en,pt,Settings,Configuración,button,text  # Button text
```

Glossaries include context awareness via suggestion system.

## Troubleshooting

**Dashboard won't start**: `pip install flask`

**QA validation fails**: Check CSV for errors indicated in report (empty cells, unchanged text, etc.)

**HTML validation fails**: Check for English fallback (missing translations), broken links, or entity issues

**SQLite threading errors**: Each worker thread gets its own database connection

**Pipeline stops at import prompt**: Type "yes" to import, "no" to review CSVs first

## Advanced Workflows

**Skip import, review only:**
```bash
python batch_translate.py pipeline --skip-generation
# Runs sync and validation, stops for manual review
```

**Auto-import if validation passes:**
```bash
python batch_translate.py pipeline --auto-import
# Skips "Import now?" prompt
```

**Force re-extract (ignore change detection):**
```bash
python batch_translate.py pipeline --force
# Extracts all files, even unchanged ones
```

## Performance Notes

- **Sync Command**: ~20-30 files/second with 4 workers
- **CSV Size**: Typical batch 50-200 KB (small CSV files)
- **Dashboard Memory**: ~20 MB lightweight
- **State Database**: < 1 MB even with 1000s of files tracked
- **Glossary Export**: ~100-200 entries per language, JSON format

## License

Provided as-is for multilingual website translation needs.
