from __future__ import annotations

from typing import List, Tuple, Dict, Any, Optional
import math

from core.surface_compat import get_surface_geometry_values

def _canonical_surface_geom(surface: Dict[str, Any], led_len: int = 0) -> tuple[int, list | None]:
    _kind, count, _width, _height = get_surface_geometry_values(surface, default_kind='strip', default_count=max(1, int(led_len) or 1))
    coords = surface.get("coords")
    if not (isinstance(coords, list) and len(coords) == count):
        coords = None
    return int(count), coords

def nearest_surface_led_index(surface: Dict[str, Any], x: float, y: float) -> int:
    """Return nearest LED index to (x,y) in surface-space.

    Uses surface['coords'] if available, else assumes strip index mapped along x.
    """
    n, coords = _canonical_surface_geom(surface)
    if isinstance(coords, list) and coords:
        best_i = 0
        best_d2 = 1e18
        for i, c in enumerate(coords):
            try:
                cx, cy = float(c[0]), float(c[1])
            except Exception:
                continue
            dx = cx - x
            dy = cy - y
            d2 = dx*dx + dy*dy
            if d2 < best_d2:
                best_d2 = d2
                best_i = i
        return int(best_i)
    # fallback: strip
    if n <= 0:
        return 0
    i = int(round(max(0.0, min(1.0, x)) * (n - 1)))
    return i

def splat_scalar_to_surface_leds(surface: Dict[str, Any], led_out: List[float], x: float, y: float, v: float, radius: float = 2.0) -> None:
    """Deposit scalar value into led_out with soft falloff in surface-space."""
    n, coords = _canonical_surface_geom(surface)
    if isinstance(coords, list) and coords:
        r2 = float(radius) * float(radius)
        for i, c in enumerate(coords):
            try:
                cx, cy = float(c[0]), float(c[1])
            except Exception:
                continue
            dx = cx - x
            dy = cy - y
            d2 = dx*dx + dy*dy
            if d2 > r2:
                continue
            w = 1.0 - math.sqrt(d2) / float(radius)
            led_out[i] += v * w
        return
    # strip fallback
    i = nearest_surface_led_index(surface, x, y)
    if 0 <= i < len(led_out):
        led_out[i] += v

# Compatibility wrappers for older layout-named callers.
def _canonical_layout_geom(layout: Dict[str, Any], led_len: int = 0) -> tuple[int, list | None]:
    return _canonical_surface_geom(layout, led_len)

def nearest_led_index(layout: Dict[str, Any], x: float, y: float) -> int:
    return nearest_surface_led_index(layout, x, y)

def splat_scalar_to_leds(layout: Dict[str, Any], led_out: List[float], x: float, y: float, v: float, radius: float = 2.0) -> None:
    return splat_scalar_to_surface_leds(layout, led_out, x, y, v, radius)

def normalize_led_buffer(buf: List[float], clamp_min: float = 0.0, clamp_max: float = 1.0) -> None:
    mn = float(clamp_min)
    mx = float(clamp_max)
    for i, v in enumerate(buf):
        if v < mn: buf[i] = mn
        elif v > mx: buf[i] = mx
