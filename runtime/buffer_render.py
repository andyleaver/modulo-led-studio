from __future__ import annotations

"""
buffer_render_v1

Reusable renderer for ScalarBuffer / VectorBuffer -> LED framebuffer.

This is an engine primitive (not an effect):
- Works with strip or cells surfaces (uses surface coords when present).
- Produces RGB tuples (0..255).
- Keeps mapping logic isolated so buffers become first-class substrates.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Sequence, Any
import math

from core.surface_compat import get_surface_geometry_values

from .shader_math import clamp01, hsv_to_rgb, add_rgb

RGB = Tuple[int, int, int]

def _canonical_surface_geom(surface: dict, framebuffer_len: int = 0) -> tuple[int, int, int, list | None]:
    """Return canonical runtime geometry from a surface snapshot.

    Geometry truth must come from canonical keys only: count/width/height.
    Optional coords are treated as non-authoritative extras and are only trusted
    when they match the canonical LED count.
    """
    _kind, count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=max(1, int(framebuffer_len) or 1))
    coords = surface.get("coords")
    if not (isinstance(coords, list) and len(coords) == count):
        coords = None
    return int(count), int(width), int(height), coords

@dataclass
class BufferRenderConfig:
    mode: str = "heat"          # "heat" | "mono" | "hue" | "vector"
    gain: float = 1.0           # scales sampled scalar before mapping
    additive: bool = True       # add on top of existing framebuffer
    mono_color: RGB = (255, 255, 255)
    alpha: float = 1.0          # 0..1

def _surface_bounds(surface: dict, framebuffer_len: int = 0) -> Tuple[float, float, float, float]:
    count, width, height, coords = _canonical_surface_geom(surface, framebuffer_len)
    if coords:
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
    if width > 1 and height > 1:
        return (0.0, 0.0, max(0.0, float(width) - 1.0), max(0.0, float(height) - 1.0))
    return (0.0, 0.0, max(0.0, float(count) - 1.0), 0.0)

def led_to_surface_xy(i: int, surface: dict, framebuffer_len: int = 0) -> Tuple[float, float]:
    count, width, height, coords = _canonical_surface_geom(surface, framebuffer_len)
    if coords and i < len(coords):
        x, y = coords[i]
        return (float(x), float(y))
    if width > 1 and height > 1:
        ii = max(0, min(int(count) - 1, int(i))) if count > 0 else int(i)
        return (float(ii % width), float(ii // width))
    return (float(i), 0.0)

def _sample_scalar_nearest(buf: Any, x_norm: float, y_norm: float) -> float:
    bw = int(getattr(buf, "w", 0) or getattr(buf, "width", 0) or 0)
    bh = int(getattr(buf, "h", 0) or getattr(buf, "height", 0) or 0)
    if bw <= 0 or bh <= 0:
        return 0.0
    bx = int(round(clamp01(x_norm) * (bw - 1)))
    by = int(round(clamp01(y_norm) * (bh - 1)))
    data = getattr(buf, "data", None)
    if data is None:
        return 0.0
    idx = by * bw + bx
    if idx < 0 or idx >= len(data):
        return 0.0
    try:
        return float(data[idx])
    except Exception:
        return 0.0

def render_scalar_buffer_to_surface_leds(surface: dict, framebuffer: List[RGB], buf: Any, cfg: Optional[BufferRenderConfig] = None) -> None:
    """
    Renders a scalar buffer into the LED framebuffer in-place.

    buf is expected to look like ScalarBuffer: .w, .h, .data (len = w*h).
    """
    if cfg is None:
        cfg = BufferRenderConfig()
    if not framebuffer:
        return

    xmin, ymin, xmax, ymax = _surface_bounds(surface, len(framebuffer))
    dx = (xmax - xmin) if (xmax - xmin) != 0.0 else 1.0
    dy = (ymax - ymin) if (ymax - ymin) != 0.0 else 1.0

    alpha = clamp01(cfg.alpha)

    for i in range(len(framebuffer)):
        x, y = led_to_surface_xy(i, surface, len(framebuffer))
        xn = (x - xmin) / dx
        yn = (y - ymin) / dy
        v = _sample_scalar_nearest(buf, xn, yn) * float(cfg.gain)
        v = clamp01(v)

        if cfg.mode == "mono":
            rgb = (int(cfg.mono_color[0] * v) & 255,
                   int(cfg.mono_color[1] * v) & 255,
                   int(cfg.mono_color[2] * v) & 255)
        else:
            # heat/hue: map v -> hue; default heat = blue->red
            hue = (2.0/3.0) * (1.0 - v)  # 0.666.. -> 0.0
            rgb = hsv_to_rgb(hue, 1.0, v)

        if alpha < 1.0:
            rgb = (int(rgb[0] * alpha) & 255, int(rgb[1] * alpha) & 255, int(rgb[2] * alpha) & 255)

        if cfg.additive:
            framebuffer[i] = add_rgb(framebuffer[i], rgb)
        else:
            framebuffer[i] = rgb

def render_vector_buffer_to_surface_leds(surface: dict, framebuffer: List[RGB], vbuf: Any, cfg: Optional[BufferRenderConfig] = None) -> None:
    """
    Renders a vector buffer magnitude/direction into the LED framebuffer in-place.

    vbuf is expected to look like VectorBuffer: .w, .h, .vx, .vy (or .data storing tuples).
    """
    if cfg is None:
        cfg = BufferRenderConfig(mode="vector")
    if not framebuffer:
        return

    xmin, ymin, xmax, ymax = _surface_bounds(surface, len(framebuffer))
    dx = (xmax - xmin) if (xmax - xmin) != 0.0 else 1.0
    dy = (ymax - ymin) if (ymax - ymin) != 0.0 else 1.0
    alpha = clamp01(cfg.alpha)

    bw = int(getattr(vbuf, "w", 0) or 0)
    bh = int(getattr(vbuf, "h", 0) or 0)
    if bw <= 0 or bh <= 0:
        return

    # Prefer separate vx/vy arrays if present
    vx = getattr(vbuf, "vx", None)
    vy = getattr(vbuf, "vy", None)
    data = getattr(vbuf, "data", None)

    def sample_vec(xn: float, yn: float) -> Tuple[float, float]:
        bx = int(round(clamp01(xn) * (bw - 1)))
        by = int(round(clamp01(yn) * (bh - 1)))
        idx = by * bw + bx
        if idx < 0 or idx >= (bw * bh):
            return (0.0, 0.0)
        if vx is not None and vy is not None and idx < len(vx) and idx < len(vy):
            return (float(vx[idx]), float(vy[idx]))
        if data is not None and idx < len(data):
            try:
                px, py = data[idx]
                return (float(px), float(py))
            except Exception:
                return (0.0, 0.0)
        return (0.0, 0.0)

    for i in range(len(framebuffer)):
        x, y = led_to_surface_xy(i, surface, len(framebuffer))
        xn = (x - xmin) / dx
        yn = (y - ymin) / dy
        fx, fy = sample_vec(xn, yn)
        mag = math.sqrt(fx*fx + fy*fy) * float(cfg.gain)
        mag = clamp01(mag)
        ang = math.atan2(fy, fx)  # -pi..pi
        hue = (ang + math.pi) / (2.0 * math.pi)  # 0..1
        rgb = hsv_to_rgb(hue, 1.0, mag)
        if alpha < 1.0:
            rgb = (int(rgb[0] * alpha) & 255, int(rgb[1] * alpha) & 255, int(rgb[2] * alpha) & 255)
        if cfg.additive:
            framebuffer[i] = add_rgb(framebuffer[i], rgb)
        else:
            framebuffer[i] = rgb




# Compatibility wrappers for older layout-named runtime helpers.
def _canonical_layout_geom(layout: dict, framebuffer_len: int = 0) -> tuple[int, int, int, list | None]:
    return _canonical_surface_geom(layout, framebuffer_len)

def _layout_bounds(layout: dict, framebuffer_len: int = 0) -> Tuple[float, float, float, float]:
    return _surface_bounds(layout, framebuffer_len)

def _led_xy(i: int, layout: dict, framebuffer_len: int = 0) -> Tuple[float, float]:
    return led_to_surface_xy(i, layout, framebuffer_len)

def render_scalar_buffer_to_leds(layout: dict, framebuffer: List[RGB], buf: Any, cfg: Optional[BufferRenderConfig] = None) -> None:
    return render_scalar_buffer_to_surface_leds(layout, framebuffer, buf, cfg)

def render_vector_buffer_to_leds(layout: dict, framebuffer: List[RGB], vbuf: Any, cfg: Optional[BufferRenderConfig] = None) -> None:
    return render_vector_buffer_to_surface_leds(layout, framebuffer, vbuf, cfg)
