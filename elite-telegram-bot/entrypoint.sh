#!/bin/sh
set -e

echo "Starting app on port ${PORT}"

exec uvicorn src.app.web.api:app \
  --host 0.0.0.0 \
  --port "${PORT}"
