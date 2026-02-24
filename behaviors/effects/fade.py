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

def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b-a)*t)

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    n = max(1, int(num_leds))
    c1 = params.get("color", (255,0,0))
    c2 = params.get("color2", (0,0,255))
    br = float(params.get("brightness", 1.0))
    sp = float(params.get("speed", 1.0))
    # 0..1
    alpha = 0.5 * (1.0 + math.sin(t * sp * 2.0 * math.pi))
    r = _lerp(int(c1[0])&255, int(c2[0])&255, alpha)
    g = _lerp(int(c1[1])&255, int(c2[1])&255, alpha)
    b = _lerp(int(c1[2])&255, int(c2[2])&255, alpha)
    px = _apply_brightness((r,g,b), br)
    return [px]*n

def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Layerstack exporter handles this behavior; standalone emit not used.
    return ""

def register_fade():
    return register(BehaviorDef(
        "fade",
        title="Fade",
        uses=["color","color2","brightness","speed"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
