#!/usr/bin/env python3
"""Fail the build if legacy schema keys survive normalization.

This enforces Modulo's 'one truth' contract:
- legacy formats are import-only (handled in project_manager.migrate_project_dict)
- runtime must be canonical-only

We intentionally treat any surviving legacy keys as a hard error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.surface_compat import get_surface_kind_value

FORBIDDEN_LAYOUT_KEYS = {
    "w", "h", "mw", "mh", "matrix_w", "matrix_h",
    "matrix_serpentine", "matrix_flip_x", "matrix_flip_y", "matrix_rotate",
}
FORBIDDEN_LAYER_TOPLEVEL_PREFIXES = ("params.layer_",)
FORBIDDEN_LAYER_TOPLEVEL_KEYS = {"blend"}
FORBIDDEN_LAYER_PARAMS_KEYS = {"layer_opacity", "layer_enabled", "layer_blend_mode", "layer_order"}

def _check_project_dict(p: dict, *, label: str) -> list[str]:
    issues: list[str] = []

    surf = p.get("surface")
    if isinstance(surf, dict):
        bad = sorted([k for k in surf.keys() if k in FORBIDDEN_LAYOUT_KEYS])
        if bad:
            issues.append(f"{label}: surface has forbidden legacy keys: {bad}")
        raw_shape = str(surf.get("shape") or "").lower().strip()
        if raw_shape == "matrix":
            issues.append(f"{label}: surface.shape is legacy 'matrix' (must be 'cells')")
        canonical_kind = get_surface_kind_value(surf, default="strip")
        if canonical_kind == "cells" and raw_shape not in ("", "cells"):
            issues.append(f"{label}: surface.shape compatibility mirror drifted from canonical kind='cells' (got {raw_shape!r})")
        if canonical_kind == "strip" and raw_shape not in ("", "strip"):
            issues.append(f"{label}: surface.shape compatibility mirror drifted from canonical kind='strip' (got {raw_shape!r})")
        if str(surf.get("type") or "").lower().strip() == "matrix":
            issues.append(f"{label}: surface.type is legacy 'matrix' (must be 'cells')")

    leaked_layout = p.get("layout")
    if isinstance(leaked_layout, dict) and leaked_layout:
        issues.append(f"{label}: leaked root layout residue survived normalization")

    layers = p.get("layers")
    if isinstance(layers, list):
        for i, ld in enumerate(layers):
            if not isinstance(ld, dict):
                continue
            # shadow key
            if "blend" in ld:
                issues.append(f"{label}: layer[{i}] has forbidden shadow key 'blend'")
            # flattened keys
            for k in ld.keys():
                if isinstance(k, str) and k.startswith(FORBIDDEN_LAYER_TOPLEVEL_PREFIXES):
                    issues.append(f"{label}: layer[{i}] has forbidden flattened key '{k}'")
            params = ld.get("params")
            if isinstance(params, dict):
                badp = sorted([k for k in params.keys() if k in FORBIDDEN_LAYER_PARAMS_KEYS])
                if badp:
                    issues.append(f"{label}: layer[{i}].params has forbidden legacy keys: {badp}")

    return issues

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> int:
    from app.project_manager import DEFAULT_PROJECT, migrate_project_dict

    all_issues: list[str] = []

    # 1) Default project
    p0 = migrate_project_dict(json.loads(json.dumps(DEFAULT_PROJECT)))
    all_issues += _check_project_dict(p0, label="DEFAULT_PROJECT")

    # 2) Fixtures (if present)
    fixtures = ROOT / "fixtures" / "projects"
    if fixtures.exists():
        for path in sorted(fixtures.glob("*.json")):
            try:
                raw = _load_json(path)
                mig = migrate_project_dict(raw)
                all_issues += _check_project_dict(mig, label=f"fixture:{path.name}")
            except Exception as e:
                all_issues.append(f"fixture:{path.name}: failed to load/migrate: {e}")

    if all_issues:
        print("[FAIL] Legacy schema keys survived normalization:\n")
        for line in all_issues:
            print(" -", line)
        return 2

    print("[OK] No legacy schema keys survive normalization.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
