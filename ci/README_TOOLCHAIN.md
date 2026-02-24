# Toolchain Pinning (Phase 10.3)

To make CI runs reproducible, pin the toolchain versions used by:
- `tools/parity_sweep.py`
- `tools/golden_exports.py`
- `tools/compile_sanity.py`

## Files
- `ci/toolchain_versions.json` — desired version constraints
- `ci/setup_toolchain.sh` — best-effort bootstrap for CI runners

## Recommendation
Cache these between CI runs:
- PlatformIO python environment
- `~/.platformio`
- `~/.arduino15` (Arduino cores)
- arduino-cli binary
