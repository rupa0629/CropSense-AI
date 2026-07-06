#!/bin/sh
set -eu

if [ "${MIGRATE_SQLITE_TO_POSTGRES:-false}" = "true" ] \
  && [ "${CUTOVER_EXECUTION_APPROVED:-}" = "execute-once" ] \
  && [ "${CUTOVER_EXECUTION_REV:-}" = "ec4afc5" ]; then
  if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
    echo "MIGRATION_DATABASE_URL is required for one-time data migration" >&2
    exit 1
  fi
  LEGACY_SQLITE_PATH="${LEGACY_SQLITE_PATH:-/app/data/cropsense.db}"
  CUTOVER_MARKER="${CUTOVER_MARKER:-/app/data/.postgres-cutover-rehearsed}"
  if [ -f "${CUTOVER_MARKER}" ]; then
    echo "CUTOVER_REHEARSAL_ALREADY_PASSED"
  else
  if [ "${RUN_BACKUP_REHEARSAL:-false}" != "true" ]; then
    echo "RUN_BACKUP_REHEARSAL=true is required for the production cutover" >&2
    exit 1
  fi
  python scripts/rehearse_database_cutover.py sqlite \
    --sqlite "${LEGACY_SQLITE_PATH}"
  case "${MIGRATION_DATABASE_URL}" in
    postgresql://*)
      ALEMBIC_DATABASE_URL="postgresql+psycopg://${MIGRATION_DATABASE_URL#postgresql://}"
      ;;
    postgres://*)
      ALEMBIC_DATABASE_URL="postgresql+psycopg://${MIGRATION_DATABASE_URL#postgres://}"
      ;;
    *)
      ALEMBIC_DATABASE_URL="${MIGRATION_DATABASE_URL}"
      ;;
  esac
  DATABASE_URL="${ALEMBIC_DATABASE_URL}" alembic upgrade head
  python scripts/migrate_sqlite_to_postgres.py \
    --sqlite "${LEGACY_SQLITE_PATH}" \
    --postgres-url "${MIGRATION_DATABASE_URL}" \
    --execute \
    --allow-verified-existing
  python scripts/rehearse_database_cutover.py postgres \
    --postgres-url "${MIGRATION_DATABASE_URL}"
  umask 077
  printf '%s\n' "verified" > "${CUTOVER_MARKER}"
  echo "CUTOVER_REHEARSAL_PASSED"
  fi
fi

if [ "${RUN_DATABASE_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi

exec uvicorn api_server:app --host 0.0.0.0 --port "${PORT:-8000}"
