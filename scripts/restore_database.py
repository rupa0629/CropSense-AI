"""Restore a verified SQLite backup while the application is stopped."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.auth_db import _db_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("--database", help="SQLite destination; defaults to DATABASE_URL")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing restore without --confirm")

    backup = Path(args.backup).resolve()
    if not backup.is_file():
        raise SystemExit(f"Backup does not exist: {backup}")
    with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise SystemExit(f"Backup integrity check failed: {result}")

    destination = Path(args.database).resolve() if args.database else _db_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".restore.tmp")
    shutil.copy2(backup, temporary)
    temporary.replace(destination)
    print(destination.resolve())


if __name__ == "__main__":
    main()
