from __future__ import annotations

"""Modulation schema utilities (wired)

Canonical storage:
- layer['modulotors']: list[dict] (each dict is ModulationBinding.to_dict()).

Legacy compatibility:
- layer['params']['_mods'] supported as fallback, but migrations mirror to modulotors.

This module provides helpers used by preview, export, and validation.
"""

from typing import Any, Dict, List, Tuple

from app.modulation_model import ModulationBinding


def get_layer_mods(layer: Dict[str, Any]) -> List[ModulationBinding]:
    mods = layer.get("modulotors")
    if isinstance(mods, list):
        out: List[ModulationBinding] = []
        for d in mods:
            if isinstance(d, dict):
                out.append(ModulationBinding.from_dict(d).normalize())
        return out
    # legacy
    params = layer.get("params", {})
    if isinstance(params, dict) and isinstance(params.get("_mods"), list):
        out: List[ModulationBinding] = []
        for d in (params.get("_mods") or []):
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
    return (True, "OK")
