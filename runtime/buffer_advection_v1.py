from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import math

from .buffers_v1 import ScalarBufferV1, VectorBufferV1
from .vector_fields_v1 import VectorField


@dataclass
class AdvectionConfigV1:
    """Semi-Lagrangian advection config for grid buffers.

    This is an engine primitive (not an effect). Deterministic for a given field.
    """

    dt: float = 1.0 / 60.0
    steps: int = 1
    wrap: bool = False  # if True, sample wraps at edges


def _sample_scalar_bilinear(buf: ScalarBufferV1, fx: float, fy: float, wrap: bool) -> float:
    w, h = buf.w, buf.h
    if w <= 0 or h <= 0:
        return 0.0

    if wrap:
        fx = fx % w
        fy = fy % h
    else:
        if fx < 0.0 or fy < 0.0 or fx > (w - 1) or fy > (h - 1):
            return 0.0

    x0 = int(math.floor(fx))
    y0 = int(math.floor(fy))
    x1 = (x0 + 1) % w if wrap else min(x0 + 1, w - 1)
    y1 = (y0 + 1) % h if wrap else min(y0 + 1, h - 1)

    tx = fx - x0
    ty = fy - y0

    v00 = buf.get(x0, y0)
    v10 = buf.get(x1, y0)
    v01 = buf.get(x0, y1)
    v11 = buf.get(x1, y1)

    a = v00 * (1.0 - tx) + v10 * tx
    b = v01 * (1.0 - tx) + v11 * tx
    return a * (1.0 - ty) + b * ty


def advect_scalar_buffer_v1(buf: ScalarBufferV1, field: VectorField, cfg: AdvectionConfigV1) -> None:
    """Advect a scalar buffer through a vector field using semi-Lagrangian backtracing."""

    steps = max(1, int(cfg.steps))
    dt = float(cfg.dt) / steps

    for _ in range(steps):
        src = buf.data
        dst = [0.0] * (buf.w * buf.h)
        for y in range(buf.h):
            for x in range(buf.w):
                # sample field at cell center
                fx = x + 0.5
                fy = y + 0.5
                vx, vy = field.sample(fx, fy, 0.0)

                # backtrace
                bx = fx - vx * dt
                by = fy - vy * dt

                v = _sample_scalar_bilinear(buf, bx - 0.5, by - 0.5, cfg.wrap)
                dst[y * buf.w + x] = v

        buf.data = dst
        buf.clamp()


def advect_vector_buffer_v1(buf: VectorBufferV1, field: VectorField, cfg: AdvectionConfigV1) -> None:
    """Advect a vector buffer by transporting (vx,vy) through a field."""

    steps = max(1, int(cfg.steps))
    dt = float(cfg.dt) / steps

    def sample_vec_bilinear(fx: float, fy: float) -> Tuple[float, float]:
        w, h = buf.w, buf.h
        if w <= 0 or h <= 0:
            return (0.0, 0.0)
        if cfg.wrap:
            fx = fx % w
            fy = fy % h
        else:
            if fx < 0.0 or fy < 0.0 or fx > (w - 1) or fy > (h - 1):
                return (0.0, 0.0)

        x0 = int(math.floor(fx))
        y0 = int(math.floor(fy))
        x1 = (x0 + 1) % w if cfg.wrap else min(x0 + 1, w - 1)
        y1 = (y0 + 1) % h if cfg.wrap else min(y0 + 1, h - 1)
        tx = fx - x0
        ty = fy - y0

        v00x, v00y = buf.get(x0, y0)
        v10x, v10y = buf.get(x1, y0)
        v01x, v01y = buf.get(x0, y1)
        v11x, v11y = buf.get(x1, y1)

        ax = v00x * (1.0 - tx) + v10x * tx
        bx = v01x * (1.0 - tx) + v11x * tx
        ay = v00y * (1.0 - tx) + v10y * tx
        byy = v01y * (1.0 - tx) + v11y * tx

        return (ax * (1.0 - ty) + bx * ty,
                ay * (1.0 - ty) + byy * ty)

    for _ in range(steps):
        dstx = [0.0] * (buf.w * buf.h)
        dsty = [0.0] * (buf.w * buf.h)
        for y in range(buf.h):
            for x in range(buf.w):
                fx = x + 0.5
                fy = y + 0.5
                vx, vy = field.sample(fx, fy, 0.0)
                bx = fx - vx * dt
                by = fy - vy * dt
                svx, svy = sample_vec_bilinear(bx - 0.5, by - 0.5)
                i = y * buf.w + x
                dstx[i] = svx
                dsty[i] = svy

        buf.vx = dstx
        buf.vy = dsty
