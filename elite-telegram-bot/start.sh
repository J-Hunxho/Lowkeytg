#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ "${SKIP_MIGRATIONS:-0}" != "1" ]]; then
  echo "Applying database migrations..."
  alembic upgrade head
else
  echo "Skipping database migrations because SKIP_MIGRATIONS=${SKIP_MIGRATIONS}"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec uvicorn src.app.web.api:app --host "$HOST" --port "$PORT"
