# Modulo (Qt-only build)

## Launch
- `python modulo_designer.py`

## Preflight
- `python -m preflight`

Optional toggles:
- `RUN_IMPORT_AUDIT=1 python -m preflight`
- `RUN_NO_TK_AUDIT=1 python -m preflight`
- `RUN_RELEASE_GATE=1 python -m preflight`
- `RUN_SOAK=1 python -m preflight`
- `RUN_STARTUP_SMOKE=1 python -m preflight`

## Startup smoke (standalone)
- `python -m tools.startup_smoke`

- `RUN_RUNTIME_GUARD_CHECK=1 python -m preflight`

## Mask debug
- `python -m tools.mask_debug project.json mask_key --ranges`


---
## Soak / Stress

Run a soak test (no interaction required):

  python3 tools/soak_run.py --seconds 600 --fps 60

If you want to stress high LED counts, set layout count in the project before running.


---
## Cleanup helpers

Lint for forbidden version labels:

  python3 tools/lint_no_version_labels.py


---
## Release gate

See docs/RELEASE_GATE.md and optionally run:

  ./RUN_RELEASE_GATE.sh
