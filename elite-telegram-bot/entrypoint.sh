#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/app/src"

exec uvicorn app.web.api:app --host 0.0.0.0 --port "${PORT:-8080}"
