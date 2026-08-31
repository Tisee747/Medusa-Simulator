#!/usr/bin/env bash
# Restart the simulator API from the directory containing this script.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${SIMULATOR_APP_ROOT:-$SCRIPT_DIR}"
cd "$APP_ROOT"

bash "$APP_ROOT/stop.sh"
sleep 1
bash "$APP_ROOT/start.sh"
