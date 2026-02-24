#!/usr/bin/env bash
set -e

# TOOLCHAIN_PINNING: for reproducible CI, see ci/README_TOOLCHAIN.md
uo pipefail


CI_MODE=0
if [[ "${1:-}" == "--ci" ]]; then
  CI_MODE=1
  shift
fi

if [[ "$CI_MODE" == "1" ]]; then
  TS="$(date -u +%Y%m%d_%H%M%SZ)"
  ART_DIR="artifacts/${TS}"
  mkdir -p "${ART_DIR}"
  export MODULO_ARTIFACT_DIR="${ART_DIR}"
  echo "CI mode: artifacts → ${ART_DIR}"
fi

echo "== Modulo Release Gate Runner =="
echo "1) Selftests"
python3 -m selftest.run_all || true

echo
echo "2) Lint: no version labels"
python3 tools/lint_no_version_labels.py || true

echo
echo "2.4) Validate target packs"
python3 tools/validate_target_packs.py
echo "[gate] 2.45 Validate behaviors"
python3 tools/validate_behaviors.py


# 2.46 Validate asset modules
python3 tools/validate_assets.py

echo
echo "2.5) Export parity sweep"
python3 tools/parity_sweep.py --json-summary

echo
echo "2.6) Golden exports"
python3 tools/golden_exports.py


echo
echo "3) Soak test (10 min default)"
python3 tools/soak_run.py --seconds 600 --fps 60 || true

echo
echo "4) Manual steps in-app:"
echo "   - Open Diagnostics -> Run full health check"
echo "   - Open Effect Audit -> Run (detail) if needed"
echo "   - Open Export -> attempt export and verify gating/report"
echo
echo "Done."