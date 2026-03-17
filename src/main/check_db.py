import sqlite3
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "translations.db"


def main(argv: Sequence[str] | None = None) -> int:
    """Print current path mappings stored in the translation database."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        print("This program takes no arguments.")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()

        print("Path mappings in DB:")
        cursor.execute(
            "SELECT source_lang, target_lang, source_path, target_path FROM path_mappings"
        )
        for row in cursor.fetchall():
            print(f"  {row}")

        print("\nTotal count:")
        cursor.execute("SELECT COUNT(*) FROM path_mappings")
        print(f"  {cursor.fetchone()[0]} mappings")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
