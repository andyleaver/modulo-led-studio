from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

def _presets_path() -> Path:
    root = Path.home() / ".modulo"
    root.mkdir(parents=True, exist_ok=True)
    return root / "presets.json"

def load_presets() -> List[Dict[str, Any]]:
    """Return presets list: [{'name': str, 'project': dict, 'ts': float}, ...]."""
    p = _presets_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        try:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="PROJECT", code="PRESETS_LOAD_FAIL", summary="Failed to load presets", details={"path": str(p)})
        except Exception:
            pass
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        proj = item.get("project")
        if not name or not isinstance(proj, dict):
            continue
        out.append({"name": name, "project": proj, "ts": float(item.get("ts") or 0.0)})
    return out

def save_presets(presets: List[Dict[str, Any]]) -> None:
    p = _presets_path()
    try:
        p.write_text(json.dumps(presets, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        try:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="PROJECT", code="PRESETS_SAVE_FAIL", summary="Failed to save presets", details={"path": str(p)})
        except Exception:
            pass
