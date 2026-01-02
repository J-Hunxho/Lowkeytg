#!/bin/sh
set -e

echo "PORT is: ${PORT}"

exec uvicorn src.app.web.api:app \
  --host 0.0.0.0 \
  --port ${PORT}
