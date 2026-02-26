from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _cfg(spatial_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return spatial_cfg if isinstance(spatial_cfg, dict) else {}


def _layout_n(layout: Dict[str, Any]) -> int:
    try:
        return int(layout.get("num_leds") or layout.get("count") or 0)
    except Exception:
        return 0


def led_to_layout_xy(i: int, layout: Dict[str, Any]) -> Tuple[float, float]:
    """Map LED index -> layout XY (float).

    - For matrix/cells layouts with coords: uses coords[i]
    - For strip layouts: x=i, y=0

    This is intentionally lightweight and deterministic.
    """
    n = _layout_n(layout)
    if i < 0 or (n > 0 and i >= n):
        return 0.0, 0.0

    coords = layout.get("coords")
    if isinstance(coords, list) and n > 0 and len(coords) == n:
        try:
            c = coords[i]
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                return float(c[0]), float(c[1])
        except Exception:
            pass

    return float(i), 0.0


def layout_to_world(x: float, y: float, spatial_cfg: Optional[Dict[str, Any]] = None) -> Tuple[float, float]:
    """Apply world transform to layout XY.

    world = rotate(mirror(scale(layout - origin)))

    Notes:
    - Origin is applied in layout space.
    - Rotation is degrees, CCW.
    - Mirrors are applied in layout space prior to rotation.
    """
    cfg = _cfg(spatial_cfg)
    ox, oy = 0.0, 0.0
    origin = cfg.get("origin")
    if isinstance(origin, (list, tuple)) and len(origin) >= 2:
        ox = _safe_float(origin[0], 0.0)
        oy = _safe_float(origin[1], 0.0)

    sx = _safe_float(cfg.get("world_scale", 1.0), 1.0)
    rot = _safe_float(cfg.get("rotation_deg", 0.0), 0.0)
    mx = bool(cfg.get("mirror_x", False))
    my = bool(cfg.get("mirror_y", False))

    lx = (float(x) - ox)
    ly = (float(y) - oy)

    if mx:
        lx = -lx
    if my:
        ly = -ly

    lx *= sx
    ly *= sx

    if abs(rot) > 1e-9:
        r = math.radians(rot)
        cr = math.cos(r)
        sr = math.sin(r)
        wx = lx * cr - ly * sr
        wy = lx * sr + ly * cr
        return wx, wy

    return lx, ly


def world_to_layout(x: float, y: float, spatial_cfg: Optional[Dict[str, Any]] = None) -> Tuple[float, float]:
    """Inverse of layout_to_world (best-effort, deterministic)."""
    cfg = _cfg(spatial_cfg)
    ox, oy = 0.0, 0.0
    origin = cfg.get("origin")
    if isinstance(origin, (list, tuple)) and len(origin) >= 2:
        ox = _safe_float(origin[0], 0.0)
        oy = _safe_float(origin[1], 0.0)

    sx = _safe_float(cfg.get("world_scale", 1.0), 1.0)
    rot = _safe_float(cfg.get("rotation_deg", 0.0), 0.0)
    mx = bool(cfg.get("mirror_x", False))
    my = bool(cfg.get("mirror_y", False))

    wx = float(x)
    wy = float(y)

    # Undo rotation
    if abs(rot) > 1e-9:
        r = math.radians(-rot)
        cr = math.cos(r)
        sr = math.sin(r)
        lx = wx * cr - wy * sr
        ly = wx * sr + wy * cr
    else:
        lx, ly = wx, wy

    # Undo scale
    if abs(sx) < 1e-12:
        sx = 1.0
    lx /= sx
    ly /= sx

    # Undo mirrors
    if mx:
        lx = -lx
    if my:
        ly = -ly

    # Undo origin
    lx += ox
    ly += oy

    return lx, ly


def world_to_led_index(x: float, y: float, layout: Dict[str, Any], spatial_cfg: Optional[Dict[str, Any]] = None) -> int:
    """Find the nearest LED index for a world XY position.

    Uses coords when present; otherwise falls back to strip mapping.
    This is O(n) and intended for authoring/preview tools, not hot loops.
    """
    lx, ly = world_to_layout(x, y, spatial_cfg)

    n = _layout_n(layout)
    coords = layout.get("coords")
    if isinstance(coords, list) and n > 0 and len(coords) == n:
        best_i = 0
        best_d2 = None
        for i in range(n):
            c = coords[i]
            if not (isinstance(c, (list, tuple)) and len(c) >= 2):
                continue
            dx = float(c[0]) - lx
            dy = float(c[1]) - ly
            d2 = dx * dx + dy * dy
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_i = i
        return int(best_i)

    # Strip fallback: clamp to index
    ii = int(round(lx))
    if n > 0:
        ii = max(0, min(n - 1, ii))
    return ii
