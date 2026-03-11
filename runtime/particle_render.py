from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple, Optional

from core.surface_compat import get_surface_geometry_values
import math

RGB = Tuple[int, int, int]

def _canonical_surface_geom(surface: dict, framebuffer_len: int = 0) -> tuple[int, int, int, list | None]:
    """Return canonical runtime geometry from a surface snapshot."""
    _kind, count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=max(1, int(framebuffer_len) or 1))
    coords = surface.get("coords")
    if not (isinstance(coords, list) and len(coords) == count):
        coords = None
    return int(count), int(width), int(height), coords

@dataclass
class ParticleRenderConfig:
    """Engine primitive: render particle points into an LED framebuffer.

    This is NOT an effect. It is a reusable renderer that can be used by
    particles, agents, sprites, buffers, or any system that outputs point samples.
    """
    radius: float = 1.75           # gaussian radius in LED-index units (strip) or pixels (matrix coords)
    sigma: Optional[float] = None  # if None, sigma = radius/1.6
    additive: bool = True
    clamp_0_255: bool = True

def _clamp_u8(x: int) -> int:
    if x < 0: return 0
    if x > 255: return 255
    return x

def _add_rgb(a: RGB, b: RGB, clamp: bool) -> RGB:
    r = a[0] + b[0]
    g = a[1] + b[1]
    bl = a[2] + b[2]
    if clamp:
        return (_clamp_u8(r), _clamp_u8(g), _clamp_u8(bl))
    return (r, g, bl)

def _mul_rgb(c: RGB, k: float) -> RGB:
    return (int(c[0]*k), int(c[1]*k), int(c[2]*k))

def _gauss(d: float, sigma: float) -> float:
    return math.exp(-(d*d) / (2.0*sigma*sigma))

def render_points_to_surface_leds(
    *,
    surface: dict,
    framebuffer: List[RGB],
    points_xy: Iterable[Tuple[float, float]],
    colors: Optional[Iterable[RGB]] = None,
    config: ParticleRenderConfig = ParticleRenderConfig(),
) -> None:
    """Splat point samples into framebuffer using a gaussian kernel.

    - If surface has 'coords' (cells), uses euclidean distance in surface-space.
    - Otherwise (strip), uses x in [0..1] mapped to LED index and ignores y.
    """
    n, width, height, coord_list = _canonical_surface_geom(surface, len(framebuffer))
    if n <= 0:
        return

    sigma = config.sigma if (config.sigma and config.sigma > 0) else max(0.35, config.radius / 1.6)

    col_iter = iter(colors) if colors is not None else None

    for p in points_xy:
        px, py = float(p[0]), float(p[1])
        col = next(col_iter) if col_iter is not None else (255, 255, 255)

        if coord_list is None and width > 1 and height > 1:
            coord_list = [(float(i % width), float(i // width)) for i in range(n)]

        if coord_list is None:
            # strip: px expected 0..1
            x01 = px
            if x01 < 0.0: x01 = 0.0
            if x01 > 1.0: x01 = 1.0
            idx_f = x01 * (n - 1 if n > 1 else 1)
            # splat over neighbor LEDs in index space
            r = max(1, int(math.ceil(config.radius * 2.5)))
            i0 = int(math.floor(idx_f))
            for i in range(max(0, i0 - r), min(n, i0 + r + 1)):
                d = abs(i - idx_f)
                a = _gauss(d, sigma)
                if a < 0.001:
                    continue
                add = _mul_rgb(col, a)
                framebuffer[i] = _add_rgb(framebuffer[i], add, config.clamp_0_255) if config.additive else add
        else:
            # cells: distance in canonical surface space
            for i in range(n):
                cx, cy = coord_list[i]
                d = math.hypot(cx - px, cy - py)
                if d > config.radius * 3.0:
                    continue
                a = _gauss(d, sigma)
                if a < 0.001:
                    continue
                add = _mul_rgb(col, a)
                framebuffer[i] = _add_rgb(framebuffer[i], add, config.clamp_0_255) if config.additive else add

def render_particle_system_to_surface_leds(
    *,
    surface: dict,
    framebuffer: List[RGB],
    ps_state: dict,
    config: ParticleRenderConfig = ParticleRenderConfig(),
) -> None:
    """Render a ParticleSystem state dict into an LED framebuffer.

    Expects ps_state to include a list 'particles' with dicts:
      {'x':float,'y':float,'r':int,'g':int,'b':int}
    """
    parts = ps_state.get("particles", []) if isinstance(ps_state, dict) else []
    pts = []
    cols = []
    for p in parts:
        try:
            pts.append((float(p.get("x", 0.0)), float(p.get("y", 0.0))))
            cols.append((int(p.get("r",255)), int(p.get("g",255)), int(p.get("b",255))))
        except Exception:
            continue
    render_points_to_surface_leds(surface=surface, framebuffer=framebuffer, points_xy=pts, colors=cols, config=config)




def render_points_to_leds(*, layout: dict, framebuffer: List[RGB], points_xy: Iterable[Tuple[float, float]], colors: Optional[Iterable[RGB]] = None, config: ParticleRenderConfig = ParticleRenderConfig()) -> None:
    return render_points_to_surface_leds(surface=layout, framebuffer=framebuffer, points_xy=points_xy, colors=colors, config=config)


def render_particle_system_to_leds(*, layout: dict, framebuffer: List[RGB], ps_state: dict, config: ParticleRenderConfig = ParticleRenderConfig()) -> None:
    return render_particle_system_to_surface_leds(surface=layout, framebuffer=framebuffer, ps_state=ps_state, config=config)
