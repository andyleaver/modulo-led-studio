from __future__ import annotations
SHIPPED = True

from typing import List, Tuple
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int,int,int]

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def _apply_brightness(rgb, br: float):
    br = _clamp01(float(br))
    r,g,b = rgb
    return (int(r*br)&255, int(g*br)&255, int(b*br)&255)

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    n = max(1, int(num_leds))
    c = params.get("color", (255,255,255))
    br = float(params.get("brightness", 1.0))
    sp = max(0.0, float(params.get("speed", 4.0)))  # flashes per second
    duty = _clamp01(float(params.get("duty", 0.25)))
    on = True
    if sp > 0.0:
        phase = (t * sp) % 1.0
        on = phase < duty
    rgb = (int(c[0])&255, int(c[1])&255, int(c[2])&255)
    px = _apply_brightness(rgb, br) if on else (0,0,0)
    return [px]*n

def _arduino_emit(*, layout: dict, params: dict) -> str:
    return ""

def register_strobe():
    return register(BehaviorDef(
        "strobe",
        title="Strobe",
        uses=["color","brightness","speed","duty"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
