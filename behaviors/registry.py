from __future__ import annotations
from export.export_eligibility import get_eligibility, ExportStatus

REGISTRY = {}
# Back-compat alias used by older diagnostics/utilities.
EFFECTS = REGISTRY

import json
from pathlib import Path
import re

def _parse_auto_load_shipped_keys(root: Path) -> set[str]:
    """Return set of shipped effect keys by parsing behaviors/auto_load.py register_*() calls."""
    p = root/'behaviors'/'auto_load.py'
    if not p.exists():
        return set()
    txt = p.read_text(encoding='utf-8', errors='ignore')
    called = set(re.findall(r"register_([a-z0-9_]+)\(\)", txt))
    # register_all() will appear as "register_all(" in imports, but calls are register_x()
    called.discard('all')
    return called

_CAPS_CACHE = None

def load_capabilities_catalog():
    global _CAPS_CACHE
    if _CAPS_CACHE is not None:
        return _CAPS_CACHE
    root = Path(__file__).resolve().parents[1]
    p = root/'behaviors'/'capabilities_catalog.json'
    if not p.exists():
        _CAPS_CACHE = {'version':1,'effects':{}}
        return _CAPS_CACHE
    _CAPS_CACHE = json.loads(p.read_text(encoding='utf-8'))
    # Merge shipped status from behaviors/auto_load.py so UI can reliably list shipped effects
    try:
        shipped = _parse_auto_load_shipped_keys(root)
        eff = _CAPS_CACHE.setdefault('effects', {})
        for k, v in eff.items():
            if isinstance(v, dict):
                v.setdefault('shipped', k in shipped)
        # Ensure shipped keys exist in catalog at least with shipped=True
        for k in shipped:
            eff.setdefault(k, {'shipped': True})
    except Exception:
        pass
    return _CAPS_CACHE


class BehaviorDef:
    # stateful=True means preview_emit receives and may mutate EffectState

    def __init__(self, key, *, preview_emit, arduino_emit, uses=None, title=None, capabilities=None):
        self.key = str(key)
        self.title = title or self.key
        self.preview_emit = preview_emit
        self.arduino_emit = arduino_emit
        self.uses = list(uses or [])
        self.capabilities = dict(capabilities or {})

def register(defn: BehaviorDef):
    if defn.key in REGISTRY:
        raise ValueError(f"Duplicate behavior key: {defn.key}")
    if defn.preview_emit is None or defn.arduino_emit is None:
        raise ValueError(f"Behavior '{defn.key}' missing parity (preview_emit + arduino_emit required).")
    caps = load_capabilities_catalog().get('effects', {})
    if not defn.capabilities:
        defn.capabilities = dict(caps.get(defn.key, {}))
    if not defn.capabilities:
        raise ValueError(f"Behavior '{defn.key}' missing capabilities entry (behaviors/capabilities_catalog.json)")
    REGISTRY[defn.key] = defn
    return defn

def register_effect(defn: BehaviorDef):
    """Back-compat alias used by older modules."""
    return register(defn)

def get_effect(key: str):
    return REGISTRY.get(str(key))

def list_effects():
    return list(REGISTRY.keys())


def list_effect_keys():
    """Return all registered behavior keys."""
    try:
        return sorted(list(REGISTRY.keys()))
    except Exception:
        return []
