"""
Translation system configuration.
Single source of truth for all translation defaults and paths.
"""

from pathlib import Path
from paths import REPO_ROOT

SOURCE_LANG = "en"
DEFAULT_TARGET_LANGS = ["fr", "de", "pt", "nl", "es", "it", "ml", "pa", "hi"]

# Data files live outside the repo
_OUTSIDE_DIR = REPO_ROOT.parent / "photography"

DEFAULT_DB_PATH = str(_OUTSIDE_DIR / "translations.db")
DEFAULT_PATH_MAPPINGS = str(_OUTSIDE_DIR / "path_mappings.csv")
DEFAULT_OUTPUT_DIR = str(_OUTSIDE_DIR / "translations_pending")
DEFAULT_BACKUP_DIR = str(_OUTSIDE_DIR / "translations_backups")
DEFAULT_MANIFEST_DIR = str(_OUTSIDE_DIR / "translations_manifests")
DEFAULT_GLOSSARY_DIR = str(_OUTSIDE_DIR)
DEFAULT_BUILD_MANIFEST_PATH = str(_OUTSIDE_DIR / "build-manifest.json")

# Source HTML is inside the repo
DEFAULT_SOURCE_DIR = str(REPO_ROOT / "en" / "photography")
