# Assets Pipeline (Phase 9.3)

This repo supports **sprite/tile assets** as Python modules under:

- `behaviors/assets/*.py`

## Two-tier approach

1. **Source assets (human-editable):**
   - raw RGB `ASSETS` dict: `{w,h,pix}`
   - easiest to author + review

2. **Packed assets (firmware-friendly):**
   - palette + optional RLE
   - intended for low-RAM targets

You can start with source assets only. If parity/compile starts to show memory pressure,
add a packed version (palette + RLE) and update the behavior runtime to import it.

## Validator

`tools/validate_assets.py` enforces structural correctness so exports never break:

- module imports
- `ASSETS` present
- correct pixel dimensions
- RGB values in range

It also emits **warnings** when unique colors exceed 256 (palette targets).

## Templates

- `templates/sprite_asset_source_template.py`
- `templates/sprite_asset_packed_template.py`
