# Target packs

Target packs live in `export/targets/<target_id>/target.json`.

## Quick start

1. Copy the template:

- `templates/target_pack_template.json` → `export/targets/<new_id>/target.json`

2. Ensure:
- folder name matches `id`
- `emitter_module` points at a real emitter
- `capabilities` is present and truthful (SKIP is fine; missing keys is not)

## Validation

Run:

```bash
python3 tools/validate_target_packs.py
```

This is also run by `RUN_RELEASE_GATE.sh` before the parity sweep.
