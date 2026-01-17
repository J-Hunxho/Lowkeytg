#!/usr/bin/env bash
set -e

echo "PWD=$(pwd)"
echo "Listing:"
ls -la

# Find the folder that contains the "app" package (the parent of /app)
APP_PARENT="$(python - <<'PY'
import os
from pathlib import Path

start = Path.cwd()

# Search a few common roots (cwd and /app)
candidates = [start, Path("/app"), Path("/app/src")]
seen = set()

for base in candidates:
    if not base.exists():
        continue
    for p in [base] + list(base.rglob("app")):
        if p in seen:
            continue
        seen.add(p)
        if p.is_dir() and (p / "bot").exists() and (p / "__init__.py").exists():
            print(str(p.parent))
            raise SystemExit(0)

print("")  # not found
PY
)"

if [ -z "$APP_PARENT" ]; then
  echo "ERROR: Could not locate python package 'app/'."
  echo "Searched under: $(pwd), /app, /app/src"
  echo "Dump tree (depth 4):"
  find . -maxdepth 4 -type d -print
  exit 1
fi

export PYTHONPATH="$APP_PARENT"
echo "Using PYTHONPATH=$PYTHONPATH"

python -c "import sys; print('sys.path[0:5]=', sys.path[:5]); import app; print('app found at', app.__file__)"

exec uvicorn app.bot.main:app --host 0.0.0.0 --port "${PORT:-8080}"
