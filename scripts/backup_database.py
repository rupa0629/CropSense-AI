"""Create a consistent SQLite backup with retention."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.auth_db import _db_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="backups")
    parser.add_argument("--retain", type=int, default=14)
    parser.add_argument("--database", help="SQLite file; defaults to DATABASE_URL")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output / f"cropsense-{stamp}.db"

    database = Path(args.database).resolve() if args.database else _db_path()
    with sqlite3.connect(database) as source, sqlite3.connect(destination) as backup:
        source.backup(backup)
        result = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")

    backups = sorted(output.glob("cropsense-*.db"), reverse=True)
    for old_backup in backups[max(args.retain, 1) :]:
        old_backup.unlink()

    print(destination.resolve())


if __name__ == "__main__":
    main()
