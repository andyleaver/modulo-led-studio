from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

def _dims(surface: dict, num_leds: int) -> tuple[int, int]:
    w = int((surface or {}).get("width") or max(1, int(num_leds)))
    h = int((surface or {}).get("height") or 1)
    if w * h != int(num_leds):
        w = max(1, min(w, int(num_leds)))
        h = max(1, int(num_leds) // w)
        if w * h < int(num_leds):
            h += 1
    return w, h

def _index(x: int, y: int, w: int, h: int) -> int:
    x = max(0, min(w - 1, int(x)))
    y = max(0, min(h - 1, int(y)))
    return y * w + x

def _preview_emit(*, num_leds: int, params: dict, t: float, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    w, h = _dims(surface_cfg, n)
    x = int(params.get("x", 0) or 0) % max(1, w)
    y = int(params.get("y", 0) or 0) % max(1, h)
    color = params.get("color", (255, 200, 120))
    rgb = (
        int(color[0]) & 255 if isinstance(color, (list, tuple)) and len(color) > 0 else 255,
        int(color[1]) & 255 if isinstance(color, (list, tuple)) and len(color) > 1 else 200,
        int(color[2]) & 255 if isinstance(color, (list, tuple)) and len(color) > 2 else 120,
    )
    frame = [(0, 0, 0)] * n
    frame[_index(x, y, w, h)] = rgb
    return frame

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_matrix_dot():
    return register(
        BehaviorDef(
            "matrix_dot",
            title="Array Dot",
            uses=["x", "y", "color"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "Array Dot",
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
