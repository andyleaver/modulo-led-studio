#!/usr/bin/env bash
set -euo pipefail

# Modulo LED Studio runner (Linux/macOS).
# Usage:
#   ./RUN.sh --qt
#   ./RUN.sh --health
# If ./RUN.sh is not executable after unzip:
#   chmod +x RUN.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

python3 -u "$ROOT_DIR/modulo_designer.py" "$@"
