from __future__ import annotations

"""Mod Packs / Plugins Loader (v1)

Loads mods from:
  - <run_root>/mods
  - <run_root>/user_data/mods

Each mod directory must contain mod.json.
"""

import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_VERSION = 1


@dataclass
class ModLoadResult:
    mod_id: str
    name: str
    version: str
    ok: bool
    path: str
    error: str = ""


def _safe_read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _validate_manifest(m: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        api = int(m.get("api", 0) or 0)
    except Exception:
        api = 0
    if api != API_VERSION:
        return False, f"API mismatch: mod api={api} app api={API_VERSION}"
    entry = str(m.get("entry") or "").strip()
    if not entry:
        return False, "Missing entry"
    return True, ""


def discover_mod_dirs(run_root: Path) -> List[Path]:
    out: List[Path] = []
    for base in [run_root / "mods", run_root / "user_data" / "mods"]:
        if base.is_dir():
            for child in sorted(base.iterdir()):
                if child.is_dir() and (child / "mod.json").is_file():
                    out.append(child)
    return out


def _exec_entry(mod_dir: Path, entry: str) -> None:
    # Ensure the mod directory is importable
    sys.path.insert(0, str(mod_dir))
    try:
        entry_path = (mod_dir / entry).resolve()
        if entry_path.is_file():
            code = entry_path.read_text(encoding="utf-8")
            g = {"__file__": str(entry_path), "__name__": f"mod_{mod_dir.name}"}
            exec(compile(code, str(entry_path), "exec"), g, g)
        else:
            __import__(entry)
    finally:
        if sys.path and sys.path[0] == str(mod_dir):
            sys.path.pop(0)


def load_mods(run_root: Path, *, quiet: bool = True) -> List[ModLoadResult]:
    results: List[ModLoadResult] = []
    for mod_dir in discover_mod_dirs(run_root):
        m = _safe_read_json(mod_dir / "mod.json") or {}
        mid = str(m.get("id") or "").strip() or mod_dir.name
        name = str(m.get("name") or mid)
        version = str(m.get("version") or "0.0.0")
        enabled = bool(m.get("enabled", True))
        if not enabled:
            results.append(ModLoadResult(mid, name, version, ok=True, path=str(mod_dir), error="DISABLED"))
            continue

        ok, why = _validate_manifest(m)
        if not ok:
            results.append(ModLoadResult(mid, name, version, ok=False, path=str(mod_dir), error=why))
            continue

        entry = str(m.get("entry") or "").strip()
        try:
            _exec_entry(mod_dir, entry)
            results.append(ModLoadResult(mid, name, version, ok=True, path=str(mod_dir)))
        except Exception as e:
            if not quiet:
                traceback.print_exc()
            results.append(ModLoadResult(mid, name, version, ok=False, path=str(mod_dir), error=f"{type(e).__name__}: {e}"))

    return results


# Health probe

def _health_probe() -> Dict[str, Any]:
    raw = os.environ.get("MODULO_MODS_LOAD", "")
    if not raw:
        return {"loaded": 0, "mods": []}
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {"loaded": 0, "mods": []}
    except Exception:
        return {"loaded": 0, "mods": [], "error": "bad MODULO_MODS_LOAD"}


def register_health_probe() -> None:
    try:
        from runtime.extensions_v1 import register_health_probe as _reg
        _reg("mods", _health_probe)
    except Exception:
        pass
