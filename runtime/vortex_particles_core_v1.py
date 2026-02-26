from __future__ import annotations

import math
from typing import List, Tuple

RGB = Tuple[int, int, int]

from runtime.shader_math_v1 import clamp01, hsv_to_rgb, gauss
from runtime.vector_fields_v1 import VortexField, VortexFieldConfig

def vortex_particles_strip_v1(
    *,
    num_leds: int,
    params: dict,
    t: float
) -> List[RGB]:
    """
    Reusable core for the classic vortex-particles strip renderer.
    Kept compatible with the prior effect visuals, but moved out of effect code.
    """
    n = max(1, int(num_leds))
    br = clamp01(float(params.get("brightness", 1.0)))
    speed = max(0.1, float(params.get("speed", 1.0)))
    density = clamp01(float(params.get("density", 0.55)))   # particle count
    softness = clamp01(float(params.get("softness", 0.45))) # trail/blur
    width = clamp01(float(params.get("width", 0.35)))       # vortex strength
    hue = float(params.get("hue", 0.65)) % 1.0

    # Particle count scaled by strip length
    count = max(6, int(n * (0.06 + density * 0.28)))
    # Vortex field around strip center in 1D coordinate mapped into 2D
    field = VortexField(VortexFieldConfig(cx=0.0, cy=0.0, strength=1.0 + 5.0 * width))

    # Precompute particle positions along [-1,1]
    pts = []
    for i in range(count):
        phase = (i / count) * math.tau
        # swirl radius modulated by time, keep deterministic from params only
        r = 0.35 + 0.25 * math.sin(t * 0.6 * speed + phase * 3.0)
        x = r * math.cos(phase + t * 0.9 * speed)
        y = r * math.sin(phase + t * 0.9 * speed)
        vx, vy = field.sample(x, y, t)
        # drift slightly along field direction to create twisting
        x += vx * 0.03
        y += vy * 0.03
        pts.append((x, y))

    # Render to strip: treat x coordinate as position, gaussian splat
    out: List[RGB] = [(0, 0, 0) for _ in range(n)]
    sigma = 0.03 + softness * 0.10
    base_rgb = hsv_to_rgb(hue, 1.0, 1.0)

    for led in range(n):
        # map led index to [-1,1]
        lx = (led / max(1, n - 1)) * 2.0 - 1.0
        acc = 0.0
        for (px, py) in pts:
            d = abs(lx - px) * (1.2 + 0.8 * abs(py))
            acc += gauss(d, sigma)
        v = clamp01(acc * (0.35 + 0.55 * density)) * br
        out[led] = (int(base_rgb[0] * v), int(base_rgb[1] * v), int(base_rgb[2] * v))

    return out
