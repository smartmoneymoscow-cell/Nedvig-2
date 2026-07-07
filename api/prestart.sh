#!/bin/bash
set -e

echo "[prestart] Running database migrations..."
alembic upgrade head
echo "[prestart] Migrations complete."

echo "[prestart] Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
