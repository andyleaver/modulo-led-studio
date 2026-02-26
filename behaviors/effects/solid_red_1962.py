from __future__ import annotations
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from export.arduino_exporter import make_solid_sketch

RGB = Tuple[int, int, int]


def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    # Era 1 (1962): a single red indicator LED.
    # We intentionally keep it parameter-free to match the onboarding gate.
    return [(255, 0, 0)] * int(num_leds)


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Export is gated off in Era 1 UI; emitter is still parity-safe.
    return make_solid_sketch(num_leds=int(layout["num_leds"]), led_pin=int(layout["led_pin"]), rgb=(255, 0, 0))


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
