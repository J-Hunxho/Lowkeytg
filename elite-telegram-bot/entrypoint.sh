#!/bin/sh
set -x
echo "PORT is $PORT"
exec uvicorn src.app.web.api:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level debug \
  --lifespan off
