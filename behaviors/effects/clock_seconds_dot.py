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

def _perimeter_points(w: int, h: int) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    if w <= 0 or h <= 0:
        return [(0, 0)]
    for x in range(w):
        pts.append((x, 0))
    for y in range(1, h):
        pts.append((w - 1, y))
    if h > 1:
        for x in range(w - 2, -1, -1):
            pts.append((x, h - 1))
    if w > 1:
        for y in range(h - 2, 0, -1):
            pts.append((0, y))
    return pts or [(0, 0)]

def _preview_emit(*, num_leds: int, params: dict, t: float, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    w, h = _dims(surface_cfg, n)
    pts = _perimeter_points(w, h)
    seconds = int(t) % 60
    idx = int(seconds * len(pts) / 60.0) % len(pts)
    color = params.get("color", (255, 255, 255))
    rgb = (
        int(color[0]) & 255 if isinstance(color, (list, tuple)) and len(color) > 0 else 255,
        int(color[1]) & 255 if isinstance(color, (list, tuple)) and len(color) > 1 else 255,
        int(color[2]) & 255 if isinstance(color, (list, tuple)) and len(color) > 2 else 255,
    )
    frame = [(0, 0, 0)] * n
    x, y = pts[idx]
    ii = y * w + x
    if 0 <= ii < n:
        frame[ii] = rgb
    return frame

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_clock_seconds_dot():
    return register(
        BehaviorDef(
            "clock_seconds_dot",
            title="Clock Seconds Dot",
            uses=["color"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "Clock Seconds Dot",
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
