"""
constraints_v1.py

Engine primitive: basic constraints and collisions for any entities with x,y,vx,vy.

This module is intentionally lightweight:
- Deterministic, pure math.
- No Qt / UI dependencies.
- JSON-safe configs (callers own serialization).

Used by: particles, agents, sprites, buffers (as needed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Protocol, Any
import math


@dataclass
class BoundsConfigV1:
    mode: str = "wrap"  # wrap | bounce | clamp | none
    padding: float = 0.0
    bounce: float = 0.9  # energy retained on bounce


@dataclass
class CircleObstacleV1:
    x: float
    y: float
    r: float
    bounce: float = 0.9


@dataclass
class SegmentObstacleV1:
    x0: float
    y0: float
    x1: float
    y1: float
    bounce: float = 0.9


@dataclass
class TileMaskObstacleV1:
    """Solid mask from a tilemap-like boolean grid.

    mask[y][x] truthy means solid.
    Coordinates assumed in layout/world units aligned with mask cells.
    """
    mask: Sequence[Sequence[int]]
    cell_w: float = 1.0
    cell_h: float = 1.0
    bounce: float = 0.9


class _Entity(Protocol):
    x: float
    y: float
    vx: float
    vy: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _wrap(v: float, lo: float, hi: float) -> float:
    span = hi - lo
    if span <= 0:
        return lo
    # Python % handles negatives fine
    return lo + ((v - lo) % span)


def _apply_bounds(ent: _Entity, w: float, h: float, cfg: BoundsConfigV1) -> None:
    if cfg.mode == "none":
        return
    lo_x, hi_x = 0.0 - cfg.padding, float(w) + cfg.padding
    lo_y, hi_y = 0.0 - cfg.padding, float(h) + cfg.padding

    if cfg.mode == "wrap":
        ent.x = _wrap(ent.x, lo_x, hi_x)
        ent.y = _wrap(ent.y, lo_y, hi_y)
        return

    if cfg.mode == "clamp":
        ent.x = _clamp(ent.x, lo_x, hi_x)
        ent.y = _clamp(ent.y, lo_y, hi_y)
        # damp velocity if clamped at boundary
        if ent.x in (lo_x, hi_x):
            ent.vx = 0.0
        if ent.y in (lo_y, hi_y):
            ent.vy = 0.0
        return

    if cfg.mode == "bounce":
        b = cfg.bounce
        if ent.x < lo_x:
            ent.x = lo_x
            ent.vx = abs(ent.vx) * b
        elif ent.x > hi_x:
            ent.x = hi_x
            ent.vx = -abs(ent.vx) * b
        if ent.y < lo_y:
            ent.y = lo_y
            ent.vy = abs(ent.vy) * b
        elif ent.y > hi_y:
            ent.y = hi_y
            ent.vy = -abs(ent.vy) * b
        return

    # unknown mode -> treat as none


def _collide_circle(ent: _Entity, c: CircleObstacleV1) -> None:
    dx = ent.x - c.x
    dy = ent.y - c.y
    rr = c.r * c.r
    d2 = dx * dx + dy * dy
    if d2 <= 1e-12 or d2 >= rr:
        return
    d = math.sqrt(d2)
    nx, ny = dx / d, dy / d
    # push out
    ent.x = c.x + nx * c.r
    ent.y = c.y + ny * c.r
    # reflect velocity
    vn = ent.vx * nx + ent.vy * ny
    if vn < 0:
        ent.vx = ent.vx - (1.0 + c.bounce) * vn * nx
        ent.vy = ent.vy - (1.0 + c.bounce) * vn * ny


def _collide_segment(ent: _Entity, s: SegmentObstacleV1) -> None:
    # project point to segment
    ax, ay, bx, by = s.x0, s.y0, s.x1, s.y1
    abx, aby = bx - ax, by - ay
    apx, apy = ent.x - ax, ent.y - ay
    ab2 = abx * abx + aby * aby
    if ab2 <= 1e-12:
        return
    t = (apx * abx + apy * aby) / ab2
    t = _clamp(t, 0.0, 1.0)
    px, py = ax + t * abx, ay + t * aby
    dx, dy = ent.x - px, ent.y - py
    d2 = dx * dx + dy * dy
    # simple "thickness" of 0.5 units
    thick = 0.5
    if d2 <= 1e-12 or d2 > thick * thick:
        return
    d = math.sqrt(d2)
    nx, ny = dx / d, dy / d
    ent.x = px + nx * thick
    ent.y = py + ny * thick
    vn = ent.vx * nx + ent.vy * ny
    if vn < 0:
        ent.vx = ent.vx - (1.0 + s.bounce) * vn * nx
        ent.vy = ent.vy - (1.0 + s.bounce) * vn * ny


def _tile_solid(tile: TileMaskObstacleV1, x: float, y: float) -> bool:
    if not tile.mask:
        return False
    tx = int(math.floor(x / tile.cell_w))
    ty = int(math.floor(y / tile.cell_h))
    if ty < 0 or ty >= len(tile.mask):
        return False
    row = tile.mask[ty]
    if tx < 0 or tx >= len(row):
        return False
    return bool(row[tx])


def _collide_tilemask(ent: _Entity, tile: TileMaskObstacleV1) -> None:
    # If inside solid, push out along velocity opposite (cheap, deterministic)
    if not _tile_solid(tile, ent.x, ent.y):
        return
    # step back a little
    ent.x -= ent.vx * 0.05
    ent.y -= ent.vy * 0.05
    ent.vx *= -tile.bounce
    ent.vy *= -tile.bounce


def apply_constraints(
    entities: Iterable[_Entity],
    *,
    width: float,
    height: float,
    bounds: Optional[BoundsConfigV1] = None,
    circles: Optional[Sequence[CircleObstacleV1]] = None,
    segments: Optional[Sequence[SegmentObstacleV1]] = None,
    tilemask: Optional[TileMaskObstacleV1] = None,
) -> None:
    """Apply constraints in-place to entities.

    This is intentionally order-stable and deterministic.
    """
    bcfg = bounds or BoundsConfigV1(mode="none")
    circles = circles or ()
    segments = segments or ()

    for ent in entities:
        _apply_bounds(ent, width, height, bcfg)
        for c in circles:
            _collide_circle(ent, c)
        for s in segments:
            _collide_segment(ent, s)
        if tilemask is not None:
            _collide_tilemask(ent, tilemask)
