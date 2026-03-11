from __future__ import annotations

"""Modulation schema utilities (wired)

Canonical storage:
- layer['modulotors']: list[dict] (each dict is ModulationBinding.to_dict()).

Legacy policy:
- layer['params']['_mods'] is migration-only and must be removed by project
  normalization before runtime/export/preview.

This module provides helpers used by preview, export, and validation.
"""

from typing import Any, Dict, List, Tuple

from app.modulation_model import ModulationBinding
from runtime.canonical_addr import canonicalize_address

def classify_mod_target(target: str) -> str:
    """Return canonical destination class for a modulotor target.

    - layer_field / project_postfx / operator_param for first-class canonical doors
    - effect_param for layer effect params that are not part of the resolver registry
    - invalid for blank/unknown values
    """
    raw = str(target or "").strip()
    if not raw:
        return "invalid"
    tgt = canonicalize_address(raw)
    if tgt is not None:
        return str(tgt.scope)
    # non-canonical names without a namespace are effect-param targets
    if "." not in raw and "[" not in raw and "]" not in raw:
        return "effect_param"
    return "invalid"

def get_layer_mods(layer: Dict[str, Any]) -> List[ModulationBinding]:
    mods = layer.get("modulotors")
    if isinstance(mods, list):
        out: List[ModulationBinding] = []
        for d in mods:
            if isinstance(d, dict):
                out.append(ModulationBinding.from_dict(d).normalize())
        return out
    return []

def set_layer_mods(layer: Dict[str, Any], mods: List[ModulationBinding]) -> None:
    layer["modulotors"] = [m.normalize().to_dict() for m in (mods or [])]

def validate_layer_mods(layer: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        mods = get_layer_mods(layer)
    except Exception:
        return (False, "Invalid modulotors structure")
    for m in mods:
        if not m.target:
            return (False, "Modulotor missing target parameter key")
        if not m.source:
            return (False, "Modulotor missing source")
        cls = classify_mod_target(m.target)
        if cls == "invalid":
            return (False, f"Modulotor target is not canonical/effect-local: {m.target}")
    return (True, "OK")
