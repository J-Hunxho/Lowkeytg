#!/bin/sh
set -e

PORT="${PORT:-8080}"

echo "Starting FastAPI on port ${PORT}"

exec uvicorn app.web.api:app \
  --app-dir /app/src \
  --host 0.0.0.0 \
  --port "${PORT}"
