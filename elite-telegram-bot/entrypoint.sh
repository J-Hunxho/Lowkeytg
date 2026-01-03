#!/bin/sh
set -e

PORT=8080
echo "Starting on port ${PORT}"

exec uvicorn src.app.web.api:app \
  --host 0.0.0.0 \
  --port 8080
