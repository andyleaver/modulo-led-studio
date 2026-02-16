#!/usr/bin/env bash
set -euo pipefail

echo "== Modulo Release Gate Runner =="
echo "1) Selftests"
python3 -m selftest.run_all || true

echo
echo "2) Lint: no version labels"
python3 tools/lint_no_version_labels.py || true

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
