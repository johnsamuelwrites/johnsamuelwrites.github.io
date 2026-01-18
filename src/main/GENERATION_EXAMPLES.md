# HTML Generation Examples

## Common Use Cases

### 1. Preview Changes (Dry-Run)

Check what would be generated before making changes:

```bash
python html_generator.py translate-dir --source-dir en/photography --target-lang fr --dry-run
```

Output:
```
[DRY-RUN MODE] Showing what would be generated:

[DRY-RUN] Would create: fr/photographie/villes/France/Lyon.html
[DRY-RUN] Would overwrite: fr/photographie/villes/Suède/Stockholm.html
[DRY-RUN] Would create: fr/photographie/villes/France/Paris.html

[DRY-RUN] Would generate 3 files
```

### 2. Generate New Translations (With Confirmation)

Generate files with confirmation for existing ones (default behavior):

```bash
python html_generator.py translate-dir --source-dir en/photography --target-lang fr
```

If a file exists, you'll be prompted:
```
File exists: fr/photographie/Stockholm.html
Overwrite? [y/N/a/q] (y=yes, N=no, a=all, q=quit): N
Skipped: fr/photographie/Stockholm.html
```

### 3. Regenerate All Files (No Confirmation)

Regenerate all files without prompts:

```bash
python html_generator.py translate-dir --source-dir en/photography --target-lang de --no-confirm
```

This overwrites all existing files automatically.

### 4. Generate Single File

```bash
# With confirmation (default)
python html_generator.py translate-file --source-file en/photography/cities/Sweden/Stockholm.html --target-lang fr

# Without confirmation
python html_generator.py translate-file --source-file en/photography/cities/Sweden/Stockholm.html --target-lang fr --no-confirm
```

### 5. Protect Manual Translations

**Workflow for manually translated files:**

1. First, check what exists:
```bash
python html_generator.py translate-dir --source-dir en/photography --target-lang fr --dry-run
```

2. Generate with confirmation (default):
```bash
python html_generator.py translate-dir --source-dir en/photography --target-lang fr
```

3. For each existing file, choose:
   - `N` - Skip (keeps your manual translation)
   - `y` - Overwrite (replaces with auto-generated)
   - `a` - Overwrite all remaining files
   - `q` - Quit and cancel

**Result**: Manual translations are preserved by selecting 'N' when prompted.

## Workflow Examples

### Safe Update Workflow

When you've updated English source files and want to regenerate translations safely:

```bash
# 1. Preview what would change
python html_generator.py translate-dir --source-dir en/photography --target-lang de --dry-run

# 2. Generate with confirmation
python html_generator.py translate-dir --source-dir en/photography --target-lang de

# 3. For each existing file, decide whether to overwrite
```

### Bulk Regeneration Workflow

When you've added many new translations and want to regenerate everything:

```bash
# Generate for all languages without confirmation
for lang in fr de pt nl es it; do
    echo "Generating $lang..."
    python html_generator.py translate-dir --source-dir en/photography --target-lang $lang --no-confirm
done
```

### Mixed Manual/Auto Translation Workflow

When you have some manual translations and want to auto-generate the rest:

```bash
# 1. Dry-run to see status
python html_generator.py translate-dir --source-dir en/photography --target-lang fr --dry-run

# 2. Generate with confirmation
python html_generator.py translate-dir --source-dir en/photography --target-lang fr

# 3. During generation:
#    - Press 'N' for manually translated files (keeps your work)
#    - Press 'y' for auto-generated files (updates them)
```

## Command Reference

### translate-file

```bash
python html_generator.py translate-file \
    --source-file <path> \
    --target-lang <lang> \
    [--output <path>] \
    [--dry-run] \
    [--no-confirm] \
    [--no-rewrite-links]
```

### translate-dir

```bash
python html_generator.py translate-dir \
    --source-dir <path> \
    --target-lang <lang> \
    [--pattern <glob>] \
    [--dry-run] \
    [--no-confirm] \
    [--no-rewrite-links]
```

**Flags:**
- `--dry-run` - Preview without writing files
- `--no-confirm` - Skip overwrite confirmation prompts
- `--no-rewrite-links` - Don't rewrite internal links (use original paths)
- `--pattern` - Custom glob pattern (default: `**/*.html`)

## Tips

1. **Always dry-run first** when unsure:
   ```bash
   python html_generator.py translate-dir --source-dir en --target-lang fr --dry-run
   ```

2. **Protect manual work** by using default confirmation mode

3. **Batch regeneration** with `--no-confirm` when you're confident

4. **Press 'q' anytime** during confirmation to cancel and preserve all remaining files
