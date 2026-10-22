#!/bin/sh
set -e

echo "[Entrypoint] Running database pre-flight checks and migrations..."
python scripts/run_migrations.py

echo "[Entrypoint] Launching application command: $@"
exec "$@"
