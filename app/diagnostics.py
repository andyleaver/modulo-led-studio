from __future__ import annotations

import sys
import platform
import json
from pathlib import Path

from behaviors.registry import load_capabilities_catalog
from app.project_model import get_surface_kind

ROOT = Path(__file__).resolve().parents[1]

def gather() -> dict:
    shipped = 0
    try:
        auto = ROOT / "behaviors" / "auto_load.py"
        if auto.exists():
            import re
            t = auto.read_text(encoding="utf-8", errors="ignore")
            shipped = len(set(re.findall(r"register_([a-z0-9_]+)\(\)", t)) - {"all"})
    except Exception:
        shipped = -1

    fixtures = len(list((ROOT / "fixtures").glob("export_smoke_*.json"))) if (ROOT/"fixtures").exists() else 0
    effects = len(list((ROOT / "behaviors" / "effects").glob("*.py"))) if (ROOT/"behaviors/effects").exists() else 0

    gold_exp = (ROOT / "goldens" / "export").exists()
    gold_prev = (ROOT / "goldens" / "preview").exists()
    goldens_export = len(list((ROOT / "goldens" / "export").glob("*.txt"))) if gold_exp else 0
    goldens_preview = len(list((ROOT / "goldens" / "preview").glob("*.txt"))) if gold_prev else 0

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "project_root": str(ROOT),
        "counts": {
            "effects": effects,
            "fixtures_export_smoke": fixtures,
            "shipped_effects": shipped,
            "goldens_export": goldens_export,
            "goldens_preview": goldens_preview,
        }
    }

def as_text() -> str:
    d = gather()
    return json.dumps(d, indent=2)

def _layout_incompat_layers(project: dict) -> int:
    try:
        kind = str(get_surface_kind(project if isinstance(project, dict) else {}) or '').strip().lower() or None
    except Exception:
        return 0
    if kind not in ("strip","cells"):
        return 0
    caps = (load_capabilities_catalog() or {}).get("effects", {}) or {}
    bad = 0
    for layer in (project.get("layers") or []):
        key = str(layer.get("behavior") or "").strip()
        if not key:
            continue
        supports = str((caps.get(key) or {}).get("supports","both"))
        if kind == "strip" and supports not in ("strip","both"):
            bad += 1
        if kind == "cells" and supports not in ("cells","both"):
            bad += 1
    return bad

def layout_incompat_summary(project: dict) -> dict:
    """Lightweight diagnostic: count layers whose behavior does not support the current canonical surface kind."""
    try:
        bad = _layout_incompat_layers(project if isinstance(project, dict) else {})
        return {"layout_incompat_layers": int(bad)}
    except Exception:
        return {"layout_incompat_layers": 0}
