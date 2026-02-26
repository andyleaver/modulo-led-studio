from __future__ import annotations

"""
Integrators v1 (engine primitive)

Shared integration helpers for particles/agents/any entity with x,y,vx,vy.

Design goals:
- Deterministic given deterministic dt + initial state
- Minimal allocations
- Safe bounds handling (wrap or clamp)
"""

from dataclasses import dataclass
from typing import Iterable, Tuple, Protocol

def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v

def wrap(v: float, lo: float, hi: float) -> float:
    span = hi - lo
    if span <= 0:
        return lo
    # Python % handles negatives; keep within [lo, hi)
    return lo + ((v - lo) % span)

class HasKinematics(Protocol):
    x: float
    y: float
    vx: float
    vy: float

@dataclass
class IntegratorConfigV1:
    """Config shared across integrators."""
    friction: float = 0.0            # 0..1 (per second-ish)
    speed_limit: float | None = None # optional clamp of speed magnitude
    wrap_edges: bool = True
    bounds: Tuple[float,float,float,float] = (0.0,0.0,1.0,1.0)  # x0,y0,x1,y1 (inclusive-ish)

def apply_drag(vx: float, vy: float, dt: float, friction: float) -> tuple[float,float]:
    fr = clamp(float(friction), 0.0, 1.0)
    if fr <= 0.0 or dt <= 0.0:
        return vx, vy
    drag = max(0.0, 1.0 - fr * dt)
    return vx * drag, vy * drag

def clamp_speed(vx: float, vy: float, limit: float | None) -> tuple[float,float]:
    if limit is None:
        return vx, vy
    lim = float(limit)
    if lim <= 0:
        return 0.0, 0.0
    s2 = vx*vx + vy*vy
    if s2 <= lim*lim:
        return vx, vy
    import math
    s = math.sqrt(s2)
    if s <= 1e-9:
        return 0.0, 0.0
    k = lim / s
    return vx*k, vy*k

def euler_step_entities(entities: Iterable[HasKinematics], dt: float, cfg: IntegratorConfigV1) -> None:
    """In-place Euler integration for entities."""
    dt = float(dt)
    if dt <= 0:
        return
    x0,y0,x1,y1 = cfg.bounds
    hi_x = x1 + 1e-6
    hi_y = y1 + 1e-6
    for e in entities:
        e.vx, e.vy = apply_drag(e.vx, e.vy, dt, cfg.friction)
        e.vx, e.vy = clamp_speed(e.vx, e.vy, cfg.speed_limit)
        e.x += e.vx * dt
        e.y += e.vy * dt
        if cfg.wrap_edges:
            e.x = wrap(e.x, x0, hi_x)
            e.y = wrap(e.y, y0, hi_y)
        else:
            e.x = clamp(e.x, x0, x1)
            e.y = clamp(e.y, y0, y1)
