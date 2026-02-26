#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

BUILD_ID_FILE="$HERE/BUILD_ID.txt"
BUILD_ID="unknown"
if [[ -f "$BUILD_ID_FILE" ]]; then
  BUILD_ID="$(cat "$BUILD_ID_FILE" | head -n 1 | tr -d '\r\n')"
fi

echo "[Modulo] BUILD_ID: ${BUILD_ID}"
echo "[Modulo] RUN_ROOT: ${HERE}"

# Anti-misrun guard: if extracted folder name doesn't match BUILD_ID, refuse to run.
BASENAME="$(basename "$HERE")"
if [[ "$BUILD_ID" != "unknown" && "$BASENAME" != "$BUILD_ID" ]]; then
  echo "[Modulo] ERROR: Folder name does not match BUILD_ID.txt"
  echo "[Modulo]        Folder:  $BASENAME"
  echo "[Modulo]        BUILD_ID: $BUILD_ID"
  echo "[Modulo]        Extract the ZIP without renaming the top-level folder."
  exit 2
fi

exec python3 "$HERE/modulo_designer.py" --qt "$@"
