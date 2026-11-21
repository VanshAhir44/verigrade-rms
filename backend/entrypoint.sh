#!/usr/bin/env sh
set -e

echo "Running Alembic database migrations..."
alembic upgrade head

if [ -n "$SEED_ADMIN_PASSWORD" ]; then
  echo "Running idempotent database seed..."
  python -m app.db.seed
fi

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
