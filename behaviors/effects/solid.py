from __future__ import annotations
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from export.arduino_exporter import make_solid_sketch

RGB = Tuple[int,int,int]

def _apply_brightness(rgb, b: float):
    try:
        b = float(b)
    except Exception:
        b = 1.0
    b = 0.0 if b < 0 else (1.0 if b > 1.0 else b)
    r,g,b0 = rgb
    return (int(r*b) & 255, int(g*b) & 255, int(b0*b) & 255)

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    c = params.get("color", (255,0,0))
    br = params.get("brightness", 1.0)
    r,g,b = int(c[0])&255, int(c[1])&255, int(c[2])&255
    px = _apply_brightness((r,g,b), br)
    return [px] * int(num_leds)

def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Phase 3A: brightness applied by scaling RGB at export time (simple + parity-safe)
    c = params.get("color", (255,0,0))
    br = params.get("brightness", 1.0)
    rgb = _apply_brightness((int(c[0])&255, int(c[1])&255, int(c[2])&255), br)
    return make_solid_sketch(num_leds=int(layout["num_leds"]), led_pin=int(layout["led_pin"]), rgb=rgb)

def register_solid():
    return register(BehaviorDef(
        "solid",
        title="Solid",
        uses=["color", "brightness"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
