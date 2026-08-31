#!/usr/bin/env bash
# Replace the active server release with a clean package and restart the API.
set -Eeuo pipefail

PACKAGE_PATH="${1:-${HOME}/simulator_backend.zip}"
APP_ROOT="${SIMULATOR_APP_ROOT:-${HOME}/simulator}"
LEGACY_ROOT="${SIMULATOR_LEGACY_ROOT:-${HOME}/simulator_alpro}"
STAGING_ROOT="${HOME}/.simulator_staging"
BACKUP_ROOT="${HOME}/.simulator_backup"

if [[ ! -f "$PACKAGE_PATH" ]]; then
    echo "Package tidak ditemukan: $PACKAGE_PATH" >&2
    exit 1
fi

OLD_ROOT="$APP_ROOT"
if [[ ! -d "$OLD_ROOT" && -d "$LEGACY_ROOT" ]]; then
    OLD_ROOT="$LEGACY_ROOT"
fi

rm -rf "$STAGING_ROOT" "$BACKUP_ROOT"
mkdir -p "$STAGING_ROOT/extracted" "$STAGING_ROOT/release"
unzip -q -o "$PACKAGE_PATH" -d "$STAGING_ROOT/extracted"

SOURCE_ROOT="$STAGING_ROOT/extracted"
if [[ -d "$SOURCE_ROOT/Backend/app" ]]; then
    SOURCE_ROOT="$SOURCE_ROOT/Backend"
fi
if [[ ! -d "$SOURCE_ROOT/app" ]]; then
    echo "Struktur package tidak valid: folder app tidak ditemukan." >&2
    exit 1
fi

cp -a "$SOURCE_ROOT/." "$STAGING_ROOT/release/"
if [[ -f "$OLD_ROOT/.env" ]]; then
    cp "$OLD_ROOT/.env" "$STAGING_ROOT/release/.env"
fi

# Runtime artifacts and Python caches must never survive a clean deployment.
find "$STAGING_ROOT/release" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGING_ROOT/release" -type d -name '.pytest_cache' -prune -exec rm -rf {} +
rm -f "$STAGING_ROOT/release/simulator.log" "$STAGING_ROOT/release/simulator.pid"
chmod +x "$STAGING_ROOT/release"/*.sh

if [[ -f "$OLD_ROOT/stop.sh" ]]; then
    SIMULATOR_APP_ROOT="$OLD_ROOT" bash "$OLD_ROOT/stop.sh" || true
fi

if [[ -d "$OLD_ROOT" ]]; then
    mv "$OLD_ROOT" "$BACKUP_ROOT"
fi
mkdir -p "$(dirname "$APP_ROOT")"
mv "$STAGING_ROOT/release" "$APP_ROOT"
rm -rf "$BACKUP_ROOT" "$STAGING_ROOT" "$PACKAGE_PATH"

SIMULATOR_APP_ROOT="$APP_ROOT" bash "$APP_ROOT/start.sh"
