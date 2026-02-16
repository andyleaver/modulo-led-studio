"""Preview/Export parity contract (single source of truth for pixel math).

Phase 1 scaffolding: behavior is currently a passthrough (brightness=1, gamma=1).
Later phases will wire exporters to emit matching math.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class ParityConfig:
    brightness: float = 1.0  # 0..1
    gamma: float = 1.0       # 1.0 = passthrough


def clamp8(x: float) -> int:
    if x <= 0:
        return 0
    if x >= 255:
        return 255
    return int(x)


def apply_brightness(rgb: RGB, brightness: float) -> RGB:
    if brightness >= 0.999:
        return rgb
    r, g, b = rgb
    return (clamp8(r * brightness), clamp8(g * brightness), clamp8(b * brightness))


def apply_gamma(rgb: RGB, gamma: float) -> RGB:
    if 0.999 <= gamma <= 1.001:
        return rgb
    inv = 1.0 / max(1e-6, gamma)
    r, g, b = rgb
    return (
        clamp8(((r / 255.0) ** inv) * 255.0),
        clamp8(((g / 255.0) ** inv) * 255.0),
        clamp8(((b / 255.0) ** inv) * 255.0),
    )


def finalize_pixel(rgb: RGB, cfg: ParityConfig) -> RGB:
    out = apply_brightness(rgb, cfg.brightness)
    out = apply_gamma(out, cfg.gamma)
    return out


def blend_over(dst: RGB, src: RGB, alpha: float) -> RGB:
    if alpha <= 0.0:
        return dst
    if alpha >= 1.0:
        return src
    dr, dg, db = dst
    sr, sg, sb = src
    a = float(alpha)
    return (
        clamp8(dr * (1.0 - a) + sr * a),
        clamp8(dg * (1.0 - a) + sg * a),
        clamp8(db * (1.0 - a) + sb * a),
    )
