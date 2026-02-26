from __future__ import annotations
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from export.arduino_exporter import make_solid_sketch

RGB = Tuple[int, int, int]


def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    # Era 2 (1972): Yellow LED (credited to M. George Craford).
    return [(255, 255, 0)] * int(num_leds)


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Export is gated off until later eras; emitter is parity-safe.
    return make_solid_sketch(num_leds=int(layout["num_leds"]), led_pin=int(layout["led_pin"]), rgb=(255, 255, 0))


def register_solid_yellow_1972():
    return register(
        BehaviorDef(
            "solid_yellow_1972",
            title="1972 Yellow LED",
            uses=[],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "1972 Yellow LED",
                "supports": "both",
                "supports_strip": True,
                "supports_matrix": True,
                "requires_audio": False,
                "shipped": True,
                "ui_category": "era",
            },
        )
    )
