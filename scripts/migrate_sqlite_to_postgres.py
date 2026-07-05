"""Copy CropSense data from SQLite to an empty PostgreSQL schema.

The command is dry-run by default. It never prints row contents and refuses to
write into non-empty target tables.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql

TABLES = (
    "users",
    "user_settings",
    "analysis_logs",
    "weather_logs",
    "chat_logs",
    "refresh_tokens",
    "password_reset_tokens",
    "prediction_feedback",
    "agronomist_review_queue",
)
IDENTITY_TABLES = {
    "users",
    "analysis_logs",
    "weather_logs",
    "chat_logs",
    "refresh_tokens",
    "password_reset_tokens",
    "prediction_feedback",
    "agronomist_review_queue",
}


def sqlite_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def postgres_columns(connection: psycopg.Connection, table: str) -> list[str]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return [row[0] for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--postgres-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the transfer. Without this flag only counts and schema compatibility are checked.",
    )
    args = parser.parse_args()

    source_path = Path(args.sqlite).resolve()
    if not source_path.is_file():
        raise SystemExit(f"SQLite source does not exist: {source_path}")
    if not args.postgres_url or not args.postgres_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("A PostgreSQL --postgres-url or DATABASE_URL is required")

    with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        with psycopg.connect(args.postgres_url) as target:
            plans: list[tuple[str, list[str], int]] = []
            for table in TABLES:
                source_cols = sqlite_columns(source, table)
                target_cols = postgres_columns(target, table)
                if not source_cols:
                    continue
                if not target_cols:
                    raise SystemExit(f"Target migration is missing table: {table}")
                columns = [column for column in source_cols if column in target_cols]
                source_count = int(source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                target_count = int(
                    target.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
                )
                if target_count:
                    raise SystemExit(f"Refusing migration: target table {table} contains {target_count} rows")
                plans.append((table, columns, source_count))

            for table, columns, count in plans:
                print(f"{table}: {count} row(s), {len(columns)} compatible column(s)")

            if not args.execute:
                print("Dry run complete. Re-run with --execute during the approved maintenance window.")
                target.rollback()
                return

            for table, columns, expected_count in plans:
                if not expected_count:
                    continue
                rows = source.execute(
                    f'SELECT {", ".join(f"""\"{column}\"""" for column in columns)} FROM "{table}"'
                ).fetchall()
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                target.executemany(statement, [tuple(row[column] for column in columns) for row in rows])

            for table in IDENTITY_TABLES:
                target.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence({}, 'id'), "
                        "COALESCE((SELECT MAX(id) FROM {}), 1), "
                        "EXISTS(SELECT 1 FROM {}))"
                    ).format(
                        sql.Literal(table),
                        sql.Identifier(table),
                        sql.Identifier(table),
                    )
                )

            for table, _, expected_count in plans:
                actual_count = int(
                    target.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
                )
                if actual_count != expected_count:
                    raise RuntimeError(
                        f"Row-count verification failed for {table}: expected {expected_count}, got {actual_count}"
                    )

            print("Migration completed and all row counts verified.")


if __name__ == "__main__":
    main()
