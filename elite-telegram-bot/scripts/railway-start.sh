#!/usr/bin/env bash
set -euo pipefail

if [[ -d "/app/src" ]]; then
  export PYTHONPATH="/app/src"
elif [[ -d "$(pwd)/src" ]]; then
  export PYTHONPATH="$(pwd)/src"
fi

echo "[railway] boot sequence started"
echo "[railway] pythonpath=${PYTHONPATH:-<unset>}"

if [[ "${RUN_MIGRATIONS_ON_START:-true}" == "true" ]]; then
  echo "[railway] applying alembic migrations"
  python -m alembic upgrade head
else
  echo "[railway] skipping migrations (RUN_MIGRATIONS_ON_START=${RUN_MIGRATIONS_ON_START})"
fi

echo "[railway] starting api on 0.0.0.0:${PORT:-8080}"
exec python -m uvicorn app.web.api:app --host 0.0.0.0 --port "${PORT:-8080}"
