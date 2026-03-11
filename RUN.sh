#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

APP_ID_FILE="$HERE/APP_ID.txt"
APP_ID="unknown"
if [[ -f "$APP_ID_FILE" ]]; then
  APP_ID="$(cat "$APP_ID_FILE" | head -n 1 | tr -d '\r\n')"
fi

echo "[Modulo] APP_ID: ${APP_ID}"
echo "[Modulo] RUN_ROOT: ${HERE}"

BASENAME="$(basename "$HERE")"
if [[ "$APP_ID" != "unknown" && "$BASENAME" != "$APP_ID" ]]; then
  echo "[Modulo] ERROR: Folder name does not match APP_ID.txt"
  echo "[Modulo]        Folder:  $BASENAME"
  echo "[Modulo]        APP_ID: $APP_ID"
  echo "[Modulo]        Extract the ZIP without renaming the top-level folder."
  exit 2
fi

exec python3 "$HERE/modulo_designer.py" "$@"
