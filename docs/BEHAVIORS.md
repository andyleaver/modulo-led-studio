# Behaviors: adding new effects safely

This repo enforces an "export-first" contract: anything shipped in-app must be exportable
(or explicitly SKIPped by target capability, never silently).

## Checklist for a new behavior/effect key

1. **Implement the effect**
   - `behaviors/effects/<key>.py` (see `templates/behavior_effect_template.py`)
2. **Register it**
   - Add `register_effect("<key>")` to `behaviors/auto_load.py`
3. **Catalog it**
   - Add an entry to `behaviors/capabilities_catalog.json` under `effects`
4. **Export eligibility**
   - Add an entry to `export/export_eligibility.py`
5. **Golden fixture (recommended)**
   - Create `demos/demo_<key>_golden.json`
   - Add it to `tools/golden_exports.py` `FIXTURES`

## Validator

`python3 tools/validate_behaviors.py`

By default it validates registry/catalog/eligibility consistency for shipped keys.

For stricter enforcement on specific new effects, list their keys (one per line) in:
`tools/new_effects_watchlist.txt`

Those keys must also have a `demos/demo_<key>_golden.json` and be listed in `tools/golden_exports.py`.
