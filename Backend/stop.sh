#!/usr/bin/env bash
# Stop the simulator API using its tracked PID or a scoped fallback lookup.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${SIMULATOR_APP_ROOT:-$SCRIPT_DIR}"
cd "$APP_ROOT"
UVICORN="${SIMULATOR_UVICORN:-${HOME}/miniconda3/envs/medusa_backend/bin/uvicorn}"

if [ -f simulator.pid ]; then
    PID="$(cat simulator.pid)"

    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"

        for _ in $(seq 1 20); do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
    fi

    rm -f simulator.pid
else
    pkill -f \
        "$UVICORN app.main:app.*8011" \
        2>/dev/null || true
fi

echo "Simulator stopped"
