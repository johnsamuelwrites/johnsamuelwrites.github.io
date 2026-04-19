# HTML Generation Examples

## Using Pipeline (Recommended)

The pipeline automatically generates HTML after importing validated translations:

```bash
# Full workflow with automatic generation
python batch_translate.py pipeline --target-langs es pt

# Pipeline will:
# 1. Extract changed files
# 2. Validate CSVs (pre-import QA)
# 3. Prompt: "Import now?"
# 4. Generate HTML (only files with 100% translations)
# 5. Validate HTML (post-generation QA)
# 6. Export glossaries
```

## Manual Generation

Generate without running full pipeline:

### 1. Generate Only Fully-Translated Files (RECOMMENDED)

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete
```

Output:
```
Generating Spanish (es):
  [*] Generated: es/viajes/ciudades.html (52/52 translations)
  [*] Generated: es/viajes/países.html (117/117 translations)
  [*] Generated: es/viajes/index.html (157/157 translations)
  Skipping (incomplete): en/photography/food.html (13/19 translations)
  Skipping (incomplete): en/photography/lakes.html (13/19 translations)
  ... (44 more skipped)

Generated: 3, Regenerated: 0, Skipped: 44
```

Features:
- **100% translations guaranteed**: Only generates complete files
- **Post-generation QA**: Validates for English fallback, broken links, entity corruption
- **Overwrite protection**: Confirms before overwriting existing files

### 2. Dry-Run (Preview Without Writing)

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete --dry-run
```

Shows what would be generated without making changes.

### 3. Force Regenerate All Files

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete --force
```

Overwrites all existing files without confirmation (safe with `--require-complete`)

## Using html_generator.py (Legacy)

The older `html_generator.py` interface is still available for direct control without database integration or state tracking. Not recommended for new workflows.

## Common Use Cases

### 1. Full Translation Cycle (Sync → Validate → Generate)

Complete workflow:

```bash
# 1. Extract changed files and review in dashboard
python batch_translate.py sync --source-dir en/photography --target-langs es pt
python batch_translate.py serve --port 8000
# (Edit translations in browser)

# 2. Validate and import
python batch_translate.py validate-csv
python batch_translate.py import

# 3. Generate and validate output
python batch_translate.py generate --target-langs es pt --require-complete
python batch_translate.py validate-html --target-langs es pt
```

### 2. Preview Changes (Dry-Run)

Check what would be generated before making changes:

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete --dry-run
```

Output shows files that would be created or overwritten.

### 3. Generate With Confirmation

Default behavior asks for confirmation before overwriting:

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete
```

Prompts:
```
File exists: es/viajes/ciudades.html
Overwrite? [y/N/a/q]: 
```

### 4. Generate Without Confirmation

Skip prompts (safe with `--require-complete`):

```bash
python batch_translate.py generate --source-dir en/photography --target-langs es --require-complete --force
```

### 5. Only Generate Specific Files

Via CSV review first:

```bash
# 1. Sync and edit only specific CSVs
python batch_translate.py sync --source-dir en/photography --target-langs es
# (Edit only specific CSVs in dashboard)

# 2. Import
python batch_translate.py import

# 3. Generate (only files with imported translations will generate)
python batch_translate.py generate --target-langs es --require-complete
```

## Workflow Examples

### Pipeline Workflow (Recommended)

Complete workflow in one command:

```bash
# Terminal 1: Start dashboard
python batch_translate.py serve --port 8000

# Terminal 2: Run pipeline
python batch_translate.py pipeline --target-langs es pt --force
```

Pipeline will:
1. Sync (extract all files with `--force`)
2. Validate CSVs (QA check)
3. Prompt "Import now?" 
4. Generate HTML files
5. Validate HTML (QA check)
6. Export glossaries

### Update Workflow

When you've updated English source files and want to regenerate translations safely:

```bash
# 1. Sync changes
python batch_translate.py sync --source-dir en/photography --target-langs es pt

# 2. Review in dashboard (add missing translations)
python batch_translate.py serve --port 8000

# 3. Validate, import, and generate
python batch_translate.py validate-csv
python batch_translate.py import
python batch_translate.py generate --target-langs es pt --require-complete
python batch_translate.py validate-html --target-langs es pt
```

### Bulk Regeneration

When translations are complete and you want to regenerate all languages:

```bash
# Generate all languages
python batch_translate.py generate --target-langs es pt fr de --require-complete --force

# Validate output
python batch_translate.py validate-html --target-langs es pt fr de
```

### Partial Generation (Single Language)

Generate only one language:

```bash
python batch_translate.py generate --target-langs es --require-complete --force
python batch_translate.py validate-html --target-langs es
```

## Command Reference

### Pipeline Command (Recommended)

```bash
python batch_translate.py pipeline \
    --target-langs <lang1> <lang2> ... \
    [--auto-import] \
    [--skip-generation] \
    [--force]
```

**Flags:**
- `--target-langs` - Languages to process (required, e.g., es pt)
- `--auto-import` - Skip import prompt, auto-import if validation passes
- `--skip-generation` - Stop after import, don't generate HTML
- `--force` - Force re-extract all files (ignore change detection)

**Output:** Detailed pipeline report with all steps

### Generate Command (Manual)

```bash
python batch_translate.py generate \
    --target-langs <lang1> <lang2> ... \
    [--source-dir <path>] \
    [--require-complete] \
    [--force] \
    [--dry-run]
```

**Flags:**
- `--target-langs` - Target languages (required, e.g., es de fr)
- `--source-dir` - Source directory (default: en/photography)
- `--require-complete` - Only generate files with 100% translations (RECOMMENDED)
- `--force` - Skip overwrite confirmation prompts
- `--dry-run` - Preview without writing files

**Best practices:**
- Always use `--require-complete` to prevent incomplete translations
- Use `--force` with `--require-complete` to skip confirmations safely
- Use `--dry-run` to preview before committing

### Other Commands

```bash
python batch_translate.py sync --source-dir <path> --target-langs <langs> [--force]
python batch_translate.py validate-csv                                # Pre-import QA
python batch_translate.py import                                      # Import CSVs
python batch_translate.py validate-html --target-langs <langs>        # Post-gen QA
python batch_translate.py status                                      # View workflow state
python batch_translate.py serve --port 8000                           # Web dashboard
python batch_translate.py glossary-sync --target-langs <langs>        # Export glossaries
```

### html_generator.py (Legacy)

Not recommended for new workflows. Use `batch_translate.py generate` instead.

## Tips

1. **Use Pipeline for Complete Workflow** (simplest):
   ```bash
   python batch_translate.py pipeline --target-langs es pt
   ```

2. **Always use --require-complete** to prevent incomplete translations:
   ```bash
   python batch_translate.py generate --target-langs es --require-complete
   ```

3. **Use --dry-run to preview** before writing:
   ```bash
   python batch_translate.py generate --target-langs es --require-complete --dry-run
   ```

4. **Combine --require-complete and --force** to skip all confirmations safely:
   ```bash
   python batch_translate.py generate --target-langs es --require-complete --force
   ```

5. **Check State Before Generating**:
   ```bash
   python batch_translate.py status  # View workflow state
   ```

6. **Web Dashboard for Editing** (better than CSV editors):
   ```bash
   python batch_translate.py serve --port 8000
   # Opens browser-based inline editor with auto-save
   ```

7. **Post-Generation Validation** catches issues:
   ```bash
   python batch_translate.py validate-html --target-langs es
   # Checks for English fallback, broken links, entity corruption
   ```
