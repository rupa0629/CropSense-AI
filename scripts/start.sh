#!/bin/sh
set -eu

if [ "${RUN_DATABASE_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi

exec uvicorn api_server:app --host 0.0.0.0 --port "${PORT:-8000}"
