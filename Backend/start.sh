#!/usr/bin/env bash
# Start the simulator API with a persistent PID and log file.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${SIMULATOR_APP_ROOT:-$SCRIPT_DIR}"
cd "$APP_ROOT"

UVICORN="${SIMULATOR_UVICORN:-${HOME}/miniconda3/envs/medusa_backend/bin/uvicorn}"

if [ -f simulator.pid ] &&
   kill -0 "$(cat simulator.pid)" 2>/dev/null; then
    echo "Simulator already running: PID $(cat simulator.pid)"
    exit 0
fi

nohup "$UVICORN" \
    app.main:app \
    --host 0.0.0.0 \
    --port 8011 \
    > simulator.log 2>&1 &

echo $! > simulator.pid

echo "Simulator started: PID $(cat simulator.pid)"
