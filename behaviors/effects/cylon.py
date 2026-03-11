from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

"""Cylon / Larson Scanner

This is a *shipped alias* behavior:
- Preview parity: delegates to `scanner`.
- Arduino parity: delegates to `scanner`.

Rationale: keep UX familiar (common LED app names) without duplicating code.
"""

from behaviors.registry import BehaviorDef, register
from behaviors.effects import scanner as _base

USES = list(getattr(_base, "USES", []) or [])

def _preview_emit(*, num_leds: int, params: dict, t: float):
    return _base._preview_emit(num_leds=num_leds, params=params, t=t)

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return _base._arduino_emit(surface=surface_cfg, params=params)

def register_cylon():
    return register(BehaviorDef(
        "cylon",
        title="Cylon / Larson Scanner",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
