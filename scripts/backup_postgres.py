"""Create an encrypted PostgreSQL custom-format backup.

Requires pg_dump and BACKUP_ENCRYPTION_KEY (a Fernet key) in the backup job.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    encryption_key = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("PostgreSQL DATABASE_URL is required")
    if not encryption_key:
        raise SystemExit("BACKUP_ENCRYPTION_KEY is required")

    output_dir = Path(os.environ.get("BACKUP_OUTPUT", "backups")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"cropsense-postgres-{timestamp}.dump.encrypted"

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_backup = Path(temp_dir) / "backup.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--file", str(raw_backup), database_url],
            check=True,
        )
        subprocess.run(["pg_restore", "--list", str(raw_backup)], check=True, capture_output=True)
        destination.write_bytes(Fernet(encryption_key.encode()).encrypt(raw_backup.read_bytes()))

    print(destination)


if __name__ == "__main__":
    main()
