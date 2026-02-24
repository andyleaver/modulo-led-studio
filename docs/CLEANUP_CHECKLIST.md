# Cleanup Pass Checklist (Release R10)

This checklist is intentionally "timeless": it does not reference internal build labels.

## Naming & Terminology
- Use semantic, domain names (layer, operator, mask, zone, group, signal, rule).
- Remove legacy/fix/stage labels from filenames, symbols, comments, strings.

## Contracts & Comments
- Comments explain *why* and constraints, not development history.
- Public functions/classes have short contract docstrings (inputs/outputs/invariants).

## Single Sources of Truth
- Export eligibility is owned by `export/export_eligibility.py`.
- Parity summary + block reasons are owned by `export/parity_summary.py`.
- Audio truth is owned by `runtime/audio_service.py` and fed into `runtime/signal_bus.py`.

## Dead/Debug Removal
- Remove unused modules, abandoned experiments, and stale flags.
- Replace temporary prints with structured logging or delete them.

## Consistency
- One path for preview rendering; one path for audit rendering.
- One path for export writing; fail-loud validation.

## Run before release
- Run selftests: `python3 -m selftest.run_all`
- Run soak: `python3 tools/soak_run.py --seconds 600 --fps 60`
- Run lint checks: `python3 tools/lint_no_version_labels.py`

