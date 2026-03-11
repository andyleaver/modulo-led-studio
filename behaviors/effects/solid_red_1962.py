from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.effects._export_hw import resolve_data_pin

RGB = Tuple[int, int, int]

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    # Era 1 (1962): a single red indicator LED.
    # We intentionally keep it parameter-free to match the onboarding gate.
    return [(255, 0, 0)] * int(num_leds)

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    # Export is gated off in Era 1 UI; emitter is still parity-safe.
    from export.arduino_exporter import make_solid_sketch
    return make_solid_sketch(num_leds=int(surface_cfg["count"]), led_pin=resolve_data_pin(surface_cfg), rgb=(255, 0, 0))

def register_solid_red_1962():
    return register(
        BehaviorDef(
            "solid_red_1962",
            title="1962 Red LED",
            uses=[],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                # Minimal capabilities override is allowed, but we still also record it in the catalog.
                "title": "1962 Red LED",
                "supports": "both",
                "supports_strip": True,
                "supports_matrix": True,
                "requires_audio": False,
                "shipped": True,
                "ui_category": "era",
            },
        )
    )
