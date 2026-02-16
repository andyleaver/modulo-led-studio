# Release Gate Checklist (R11)

This document defines the minimum gate to declare Modulo LED Studio "release-ready".
It is intentionally strict and must be run on the final candidate zip/repo.

## Gate 1 — Diagnostics are authoritative
- Health Check report runs without crashing.
- Report includes:
  - Project Validation (0 errors)
  - Structural Diagnostics (dangling/invalid/empty are surfaced)
  - Audio Snapshot (mode/backend/values)
  - Effect Audit Summary (OK/BLANK/SKIP/UNSUPPORTED)
  - Targeting diagnostics results

## Gate 2 — Export truth is enforced
- Export blocks when:
  - validation errors exist
  - parity summary indicates blocked content
  - template token validation fails (fail-loud)
- Export report includes parity summary.

## Gate 3 — Preview/Audit truth
- Known-good effects light pixels and animate in:
  - live preview
  - effect audit
- Audit uses engine audio truth (no audit-only injection paths).

## Gate 4 — Stability baseline
- Soak test runs for at least 10 minutes at 60 FPS without crash:
  - `python3 tools/soak_run.py --seconds 600 --fps 60`

## Gate 5 — Cleanup compliance
- Lint for forbidden version labels passes:
  - `python3 tools/lint_no_version_labels.py`
- No dead experimental panels surfaced without "Preview-only" or "Metadata-only" labeling.

## Recommended: Selftests
- Run shipped selftests:
  - `python3 -m selftest.run_all`

## Evidence bundle for release
Store in `out/`:
- `health_check_report.txt`
- `effect_audit_detail.txt` (if available)
- `export_report.txt`
- `soak_log.txt`

