"""Decrypt and structurally verify a PostgreSQL backup without restoring production."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    args = parser.parse_args()
    key = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
    if not key:
        raise SystemExit("BACKUP_ENCRYPTION_KEY is required")
    encrypted = Path(args.backup).resolve()
    with tempfile.TemporaryDirectory() as temp_dir:
        raw = Path(temp_dir) / "verified.dump"
        raw.write_bytes(Fernet(key.encode()).decrypt(encrypted.read_bytes()))
        subprocess.run(["pg_restore", "--list", str(raw)], check=True)
    print("Backup structure verified")


if __name__ == "__main__":
    main()
