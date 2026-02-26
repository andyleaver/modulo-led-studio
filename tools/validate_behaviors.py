#!/usr/bin/env python3
"""Validate behavior/effect plumbing.

Checks:
- shipped keys parsed from behaviors/auto_load.py exist as python modules under behaviors/effects/
- shipped keys exist in behaviors/capabilities_catalog.json
- shipped keys have an entry in export/export_eligibility.py

Optional strict mode:
- keys listed in tools/new_effects_watchlist.txt must have a golden fixture and be included in tools/golden_exports.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def _fail(msg: str) -> None:
    print(f"[validate_behaviors] ERROR: {msg}")
    raise SystemExit(1)

def _warn(msg: str) -> None:
    print(f"[validate_behaviors] WARN: {msg}")

def _read_watchlist() -> list[str]:
    p = ROOT / "tools" / "new_effects_watchlist.txt"
    if not p.exists():
        return []
    keys = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.append(line)
    return keys

def main() -> int:
    # shipped keys (registry already knows how to parse auto_load)
    sys.path.insert(0, str(ROOT))
    from behaviors.registry import _parse_auto_load_shipped_keys
    from export.export_eligibility import ELIGIBILITY

    shipped = sorted(_parse_auto_load_shipped_keys(ROOT / "behaviors"))
    if not shipped:
        _fail("No shipped keys parsed from behaviors/auto_load.py")

    cat_path = ROOT / "behaviors" / "capabilities_catalog.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    effects = cat.get("effects", {})
    if not isinstance(effects, dict):
        _fail("behaviors/capabilities_catalog.json missing top-level 'effects' dict")

    effects_dir = ROOT / "behaviors" / "effects"

    missing_py = []
    missing_cat = []
    missing_elig = []
    for key in shipped:
        if not (effects_dir / f"{key}.py").exists():
            missing_py.append(key)
        if key not in effects:
            missing_cat.append(key)
        if key not in ELIGIBILITY:
            missing_elig.append(key)

    if missing_py:
        _fail(f"Missing behaviors/effects python modules for: {', '.join(missing_py[:20])}" + (" ..." if len(missing_py)>20 else ""))
    if missing_cat:
        _fail(f"Missing capabilities_catalog entries for: {', '.join(missing_cat[:20])}" + (" ..." if len(missing_cat)>20 else ""))
    if missing_elig:
        _fail(f"Missing export eligibility entries for: {', '.join(missing_elig[:20])}" + (" ..." if len(missing_elig)>20 else ""))

    # strict: new effects watchlist must have golden fixture + fixture list inclusion
    watch = _read_watchlist()
    if watch:
        ge_path = ROOT / "tools" / "golden_exports.py"
        ge_text = ge_path.read_text(encoding="utf-8")
        demos = ROOT / "demos"

        for key in watch:
            fixture = f"demo_{key}_golden.json"
            if not (demos / fixture).exists():
                _fail(f"Watchlist effect '{key}' missing demos/{fixture}")
            if fixture not in ge_text:
                _fail(f"Watchlist effect '{key}' fixture '{fixture}' not listed in tools/golden_exports.py FIXTURES")

    print(f"[validate_behaviors] OK: {len(shipped)} shipped keys validated")
    if watch:
        print(f"[validate_behaviors] OK: strict watchlist validated ({len(watch)} keys)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
