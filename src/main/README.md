# `src/main`

Python utilities used to generate, analyze, and maintain the website.

## Entry Point

Use the unified CLI:

```bash
python src/main/main.py list
python src/main/main.py <command> [args...]
```

Examples:

```bash
python src/main/main.py blog
python src/main/main.py slides en/slides/example.html
python src/main/main.py convert-thumbnails input.html output.html
python src/main/main.py verify-usage . --exclude-dirs templates analysis
```

## Available Commands

- `batch-translate`: translation workflow helper.
- `blog`: generates blog indexes and feeds.
- `build-all-search-indexes`: builds search indexes for all languages.
- `check-db`: prints translation path mappings stored in `translations.db`.
- `ci-internal-links`: CI-focused internal link verification.
- `convert-thumbnails`: rewrites Wikimedia thumbnail URLs in HTML.
- `generate-overview`: generates translation overview output.
- `html-generator`: generates translated HTML files.
- `links`: checks links in HTML files.
- `list-files`: lists files with filters.
- `metadata`: inspects HTML metadata.
- `slides`: renumbers slide navigation.
- `style`: replaces embedded CSS in HTML files.
- `template`: replaces HTML template sections.
- `translate-manager`: manages translation memory and path mappings.
- `verify-usage`: reports unreferenced local HTML files.

## Structure

- `main.py`: single dispatcher for executable tools in this folder.
- `file_rewrite.py`: shared helper for safe text-file rewrites.
- Library-style modules such as `analyse.py`, `links.py`, and `translate_manager.py` provide reusable functionality used by the command scripts.

## Development Notes

- Prefer adding new command-line tools through `main.py` so `src/main` keeps a single stable entry point.
- Avoid top-level argument parsing in reusable modules; expose `main(argv=None)` instead.
- Keep file rewrite logic centralized when possible to reduce duplication and accidental partial writes.
