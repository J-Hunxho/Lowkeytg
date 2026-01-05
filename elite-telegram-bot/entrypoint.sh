#!/bin/sh
set -e

echo "Starting FastAPI on port 8080"

exec uvicorn src.app.bot.main:app 
--host 0.0.0.0 \
--port ${PORT}
