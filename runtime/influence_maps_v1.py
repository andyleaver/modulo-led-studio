"""
Influence Maps v1 (engine primitive)

Bridge point-like entities (agents/particles/sprites) with scalar/vector buffers.
This is NOT an effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple
import math

from .buffers_v1 import ScalarBufferV1


@dataclass
class DepositConfigV1:
    radius: float = 2.0
    amount: float = 1.0
    clamp_min: float = 0.0
    clamp_max: float = 1.0
    falloff: str = "gaussian"  # gaussian | linear | flat


def _weight(dist: float, radius: float, falloff: str) -> float:
    if radius <= 0.0 or dist > radius:
        return 0.0
    if falloff == "flat":
        return 1.0
    if falloff == "linear":
        return max(0.0, 1.0 - (dist / radius))
    sigma = max(1e-6, radius * 0.5)
    return math.exp(- (dist * dist) / (2.0 * sigma * sigma))


def deposit_points_scalar_v1(buf: ScalarBufferV1,
                             points_xy: Iterable[Tuple[float, float]],
                             cfg: Optional[DepositConfigV1] = None) -> None:
    """
    Deposit scalar influence into a ScalarBufferV1 from point samples.

    points_xy are in buffer grid coords: x in [0,w), y in [0,h)
    """
    if cfg is None:
        cfg = DepositConfigV1()

    r = float(cfg.radius)
    if r <= 0.0:
        return

    w, h = buf.w, buf.h
    ox0 = int(math.floor(-r))
    ox1 = int(math.ceil(r))

    for (px, py) in points_xy:
        cx = int(round(px))
        cy = int(round(py))
        for oy in range(ox0, ox1 + 1):
            yy = cy + oy
            if yy < 0 or yy >= h:
                continue
            for ox in range(ox0, ox1 + 1):
                xx = cx + ox
                if xx < 0 or xx >= w:
                    continue
                d = math.hypot((px - xx), (py - yy))
                wt = _weight(d, r, cfg.falloff)
                if wt <= 0.0:
                    continue
                buf.set(xx, yy, buf.get(xx, yy) + cfg.amount * wt)

    # clamp (in-place)
    mn = cfg.clamp_min
    mx = cfg.clamp_max
    if mn is None and mx is None:
        return
    if mn is None:
        mn = -1e9
    if mx is None:
        mx = 1e9
    for y in range(h):
        for x in range(w):
            v = buf.get(x, y)
            if v < mn:
                buf.set(x, y, mn)
            elif v > mx:
                buf.set(x, y, mx)


@dataclass
class SenseConfigV1:
    sample_radius: float = 1.0
    eps: float = 1e-6


def sense_gradient_scalar_v1(buf: ScalarBufferV1,
                             x: float,
                             y: float,
                             cfg: Optional[SenseConfigV1] = None) -> Tuple[float, float]:
    """
    Approx gradient via central differences using bilinear sampling.
    """
    if cfg is None:
        cfg = SenseConfigV1()
    r = max(cfg.eps, float(cfg.sample_radius))
    vxp = buf.sample_bilinear(x + r, y)
    vxm = buf.sample_bilinear(x - r, y)
    vyp = buf.sample_bilinear(x, y + r)
    vym = buf.sample_bilinear(x, y - r)
    dx = (vxp - vxm) / (2.0 * r)
    dy = (vyp - vym) / (2.0 * r)
    return dx, dy


def steer_follow_gradient_v1(vx: float,
                             vy: float,
                             grad_x: float,
                             grad_y: float,
                             strength: float = 1.0,
                             max_speed: Optional[float] = None) -> Tuple[float, float]:
    """
    Steering helper: add normalized gradient direction to (vx,vy).
    """
    gx, gy = grad_x, grad_y
    gmag = math.hypot(gx, gy)
    if gmag > 1e-9:
        gx /= gmag
        gy /= gmag
        vx += gx * strength
        vy += gy * strength

    if max_speed is not None:
        sp = math.hypot(vx, vy)
        if sp > max_speed and sp > 1e-9:
            s = max_speed / sp
            vx *= s
            vy *= s
    return vx, vy
