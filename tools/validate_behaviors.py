#!/usr/bin/env python3
"""Validate behavior/effect plumbing.

Checks:
- shipped keys parsed from behaviors/auto_load.py exist as python modules under behaviors/effects/
- shipped keys exist in behaviors/capabilities_catalog.json
- shipped keys have an entry in export/export_eligibility.py

Optional strict mode:
- keys listed in tools/new_effects_watchlist.txt must have a shipped golden fixture
  under fixtures/projects/ and be included in tools/golden_exports.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "projects"


def _fail(msg: str) -> None:
    print(f"[validate_behaviors] ERROR: {msg}")
    raise SystemExit(1)


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
    sys.path.insert(0, str(ROOT))
    from behaviors.registry import _parse_auto_load_shipped_keys
    from export.export_eligibility import ELIGIBILITY
    from tools.golden_exports import FIXTURES

    shipped = sorted(_parse_auto_load_shipped_keys(ROOT))
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
        _fail(f"Missing behaviors/effects python modules for: {', '.join(missing_py[:20])}" + (" ..." if len(missing_py) > 20 else ""))
    if missing_cat:
        _fail(f"Missing capabilities_catalog entries for: {', '.join(missing_cat[:20])}" + (" ..." if len(missing_cat) > 20 else ""))
    if missing_elig:
        _fail(f"Missing export eligibility entries for: {', '.join(missing_elig[:20])}" + (" ..." if len(missing_elig) > 20 else ""))

    watch = _read_watchlist()
    if watch:
        fixture_set = set(FIXTURES)
        for key in watch:
            fixture = f"demo_{key}_golden.json"
            if not (FIXTURE_DIR / fixture).exists():
                _fail(f"Watchlist effect '{key}' missing fixtures/projects/{fixture}")
            if fixture not in fixture_set:
                _fail(f"Watchlist effect '{key}' fixture '{fixture}' not listed in tools/golden_exports.py FIXTURES")

    print(f"[validate_behaviors] OK: {len(shipped)} shipped keys validated")
    if watch:
        print(f"[validate_behaviors] OK: strict watchlist validated ({len(watch)} keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
