#!/usr/bin/env bash
set -euo pipefail

# Reproducible toolchain bootstrap (best-effort).
# This script is intended for CI runners (Linux) and expects internet access.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS="$ROOT/ci/toolchain_versions.json"

echo "Reading toolchain versions from: $VERSIONS"

# PlatformIO (pinned by pip constraint)
if command -v python3 >/dev/null 2>&1; then
  echo "Installing PlatformIO via pip (constraint from toolchain_versions.json)..."
  python3 -m pip install --upgrade pip
  python3 -m pip install "platformio==6.1.*"
else
  echo "python3 not found; skipping PlatformIO install."
fi

# Arduino CLI - user/CI should install and cache
if command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli already installed: $(arduino-cli version || true)"
else
  echo "arduino-cli not found."
  echo "Install it from official releases and cache it on your CI runner."
fi

echo "Done."
