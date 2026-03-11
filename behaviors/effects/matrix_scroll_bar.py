from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

def _dims(surface: dict, num_leds: int) -> tuple[int, int]:
    w = int((surface or {}).get("width") or max(1, int(num_leds)))
    h = int((surface or {}).get("height") or 1)
    if w * h != int(num_leds):
        w = max(1, min(w, int(num_leds)))
        h = max(1, int(math.ceil(int(num_leds) / float(w))))
    return w, h

def _idx(x: int, y: int, w: int) -> int:
    return y * w + x

def _preview_emit(*, num_leds: int, params: dict, t: float, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    w, h = _dims(surface_cfg, n)
    speed = float(params.get("speed", 0.7) or 0.7)
    thickness = max(1, int(params.get("thickness", 2) or 2))
    color = params.get("color", (255, 80, 40))
    rgb = (
        int(color[0]) & 255 if isinstance(color, (list, tuple)) and len(color) > 0 else 255,
        int(color[1]) & 255 if isinstance(color, (list, tuple)) and len(color) > 1 else 80,
        int(color[2]) & 255 if isinstance(color, (list, tuple)) and len(color) > 2 else 40,
    )
    pos = int((t * max(0.05, speed) * w) % max(1, w))
    frame = [(0, 0, 0)] * n
    for y in range(h):
        for dx in range(thickness):
            x = (pos + dx) % max(1, w)
            ii = _idx(x, y, w)
            if ii < n:
                frame[ii] = rgb
    return frame

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_matrix_scroll_bar():
    return register(
        BehaviorDef(
            "matrix_scroll_bar",
            title="Array Scroll Bar",
            uses=["speed", "thickness", "color"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "Array Scroll Bar",
                "supports": "preview",
                "supports_strip": False,
                "supports_matrix": True,
                "requires_audio": False,
                "shipped": True,
                "ui_category": "era",
                "preview_only": True,
            },
        )
    )
