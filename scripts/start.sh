#!/bin/sh
set -eu

if [ "${MIGRATE_SQLITE_TO_POSTGRES:-false}" = "true" ]; then
  if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
    echo "MIGRATION_DATABASE_URL is required for one-time data migration" >&2
    exit 1
  fi
  LEGACY_SQLITE_PATH="${LEGACY_SQLITE_PATH:-/app/data/cropsense.db}"
  DATABASE_URL="${MIGRATION_DATABASE_URL}" alembic upgrade head
  python scripts/migrate_sqlite_to_postgres.py \
    --sqlite "${LEGACY_SQLITE_PATH}" \
    --postgres-url "${MIGRATION_DATABASE_URL}" \
    --execute
fi

if [ "${RUN_DATABASE_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi

exec uvicorn api_server:app --host 0.0.0.0 --port "${PORT:-8000}"
