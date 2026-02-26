# Phase 9 → Phase 10 Checklist (Expansion → Release Hardening)

This build is based on V85 (export-safe baseline) and adds CI + artifacted gates.

## Phase 9: Expansion

### 9.1 Add a new target pack
1. Create `targets/<new_target_id>.json`
2. Required keys:
   - `id`
   - `emitter_module`
   - capability flags (`supports_matrix`, `supports_audio`, etc.)
3. Run:
   - `python3 tools/parity_sweep.py`
   - `./RUN_RELEASE_GATE.sh --ci`
4. Add a golden fixture if the target is meaningfully different (matrix vs strip, audio vs none).

### 9.2 Add a new behavior/runtime
1. Add exporter mapping (behavior id / variant via `purpose_i0`)
2. Implement deterministic firmware runtime
3. Mark eligibility EXPORTABLE
4. Add/extend a golden fixture and update baseline:
   - `python3 tools/golden_exports.py --update`

## Phase 10: Release hardening

### 10.1 Headless gate + artifacts
- `./RUN_RELEASE_GATE.sh --ci` writes all reports into `artifacts/<utc_timestamp>/`

### 10.2 CI
- GitHub Actions workflow: `.github/workflows/release-gate.yml`
- Uploads `artifacts/` for every PR/push.

### 10.3 Toolchain pinning (optional)
- Pin PlatformIO platform versions and arduino-cli cores to stabilize compilation.



## Phase 9.1B Target pack template + validator
- Template: `templates/target_pack_template.json`
- Validator: `python3 tools/validate_target_packs.py` (also runs in release gate)

## Phase 9.2 – Behavior template + validator
- templates/behavior_effect_template.py
- tools/validate_behaviors.py (wired into RUN_RELEASE_GATE.sh)
- tools/new_effects_watchlist.txt (optional strict enforcement)

## Phase 9.3 — Assets pipeline

- Use  to keep sprite/tile assets export-safe.
- Prefer source assets first, then add packed (palette/RLE) when memory dictates.

### 9.4 Add/lock a golden fixture for any new exported behavior
Use the helper:
- `python3 tools/register_golden_fixture.py --name demo_<key>_golden.json --create`
- Then run: `python3 tools/golden_exports.py --update`

## Phase 10.4 (Implemented)
- GitHub Actions tag workflow: .github/workflows/release-artifacts.yml
- On tag push (v*): runs gate, zips artifacts/, attaches to GitHub Release.

