"""Create encrypted cutover backups and verify they can be restored.

The SQLite stage creates a consistent snapshot and verifies a decrypted copy.
The PostgreSQL stage creates a custom-format dump, restores it into an isolated
temporary database, compares table row counts, and always drops that database.
No credentials, URLs, or row contents are printed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from cryptography.fernet import Fernet
from psycopg import sql

from migrate_sqlite_to_postgres import TABLES


def cipher(secret: str) -> Fernet:
    if len(secret) < 32:
        raise SystemExit("BACKUP_ENCRYPTION_KEY must contain at least 32 characters")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypted_destination(output_dir: Path, database: str, timestamp: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"cropsense-{database}-{timestamp}.encrypted"


def sqlite_stage(source_path: Path, output_dir: Path, encryption: Fernet, timestamp: str) -> None:
    if not source_path.is_file():
        raise SystemExit(f"SQLite source does not exist: {source_path}")

    destination = encrypted_destination(output_dir, "sqlite", timestamp)
    with tempfile.TemporaryDirectory() as temp_dir:
        raw_backup = Path(temp_dir) / "cropsense.db"
        restored = Path(temp_dir) / "restored.db"
        with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(raw_backup)) as backup:
            source.backup(backup)
        destination.write_bytes(encryption.encrypt(raw_backup.read_bytes()))
        restored.write_bytes(encryption.decrypt(destination.read_bytes()))
        with closing(sqlite3.connect(f"file:{restored}?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"SQLite restore integrity check failed: {result}")

    print(f"SQLite encrypted backup and restore verification passed: {destination.name}")


def database_url_with_name(database_url: str, database_name: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def table_counts(database_url: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with psycopg.connect(database_url) as connection:
        for table in TABLES:
            exists = connection.execute(
                "SELECT to_regclass(%s)",
                (f"public.{table}",),
            ).fetchone()[0]
            if exists:
                counts[table] = int(
                    connection.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                    ).fetchone()[0]
                )
    return counts


def postgres_stage(database_url: str, output_dir: Path, encryption: Fernet, timestamp: str) -> None:
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("A PostgreSQL migration URL is required")

    temporary_database = f"cropsense_restore_{timestamp.lower()}"
    destination = encrypted_destination(output_dir, "postgres", timestamp)
    maintenance_url = database_url_with_name(database_url, "postgres")
    restored_url = database_url_with_name(database_url, temporary_database)
    created = False

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_backup = Path(temp_dir) / "backup.dump"
        restored_backup = Path(temp_dir) / "restored.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(raw_backup), database_url],
            check=True,
        )
        subprocess.run(["pg_restore", "--list", str(raw_backup)], check=True, capture_output=True)
        destination.write_bytes(encryption.encrypt(raw_backup.read_bytes()))
        restored_backup.write_bytes(encryption.decrypt(destination.read_bytes()))
        subprocess.run(["pg_restore", "--list", str(restored_backup)], check=True, capture_output=True)

        try:
            with psycopg.connect(maintenance_url, autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(temporary_database)))
                created = True
            subprocess.run(
                ["pg_restore", "--no-owner", "--no-acl", "--dbname", restored_url, str(restored_backup)],
                check=True,
            )
            source_counts = table_counts(database_url)
            restored_counts = table_counts(restored_url)
            if source_counts != restored_counts:
                raise RuntimeError(
                    f"PostgreSQL restore row-count mismatch: source={source_counts}, restored={restored_counts}"
                )
        finally:
            if created:
                with psycopg.connect(maintenance_url, autocommit=True) as admin:
                    admin.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = %s AND pid <> pg_backend_pid()",
                        (temporary_database,),
                    )
                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(temporary_database)))

    print(f"PostgreSQL encrypted dump, isolated restore, and row verification passed: {destination.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("sqlite", "postgres"))
    parser.add_argument("--sqlite", default=os.getenv("LEGACY_SQLITE_PATH", "/app/data/cropsense.db"))
    parser.add_argument("--postgres-url", default=os.getenv("MIGRATION_DATABASE_URL"))
    parser.add_argument("--output", default=os.getenv("BACKUP_OUTPUT", "/app/data/backups"))
    args = parser.parse_args()

    secret = os.getenv("BACKUP_ENCRYPTION_KEY", "")
    encryption = cipher(secret)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output).resolve()

    if args.stage == "sqlite":
        sqlite_stage(Path(args.sqlite).resolve(), output_dir, encryption, timestamp)
    else:
        postgres_stage(args.postgres_url or "", output_dir, encryption, timestamp)


if __name__ == "__main__":
    main()
