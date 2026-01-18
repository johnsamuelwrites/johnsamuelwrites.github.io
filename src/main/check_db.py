import sqlite3
from pathlib import Path

# Get repository root (two levels up from this script)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
db_path = REPO_ROOT / 'translations.db'

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("Path mappings in DB:")
cursor.execute("SELECT source_lang, target_lang, source_path, target_path FROM path_mappings")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nTotal count:")
cursor.execute("SELECT COUNT(*) FROM path_mappings")
print(f"  {cursor.fetchone()[0]} mappings")

conn.close()
