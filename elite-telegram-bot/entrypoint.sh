#!/bin/sh
set -e

echo "Starting FastAPI on port 8080"

exec uvicorn src.app.web.api:app \
  --host 0.0.0.0 \
  --port 8080
