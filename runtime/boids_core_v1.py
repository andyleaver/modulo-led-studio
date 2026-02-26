from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

Vec2 = Tuple[float, float]

@dataclass
class BoidsConfigV1:
    neighbor_radius: float = 10.0
    separation_radius: float = 4.0
    max_speed: float = 20.0
    max_force: float = 30.0
    w_alignment: float = 1.0
    w_cohesion: float = 0.8
    w_separation: float = 1.2

def _limit(vx: float, vy: float, max_mag: float) -> Vec2:
    mag = math.hypot(vx, vy)
    if mag <= 1e-9 or mag <= max_mag:
        return vx, vy
    s = max_mag / mag
    return vx * s, vy * s

def _seek(px: float, py: float, tx: float, ty: float, vx: float, vy: float, cfg: BoidsConfigV1) -> Vec2:
    dx, dy = (tx - px), (ty - py)
    sx, sy = _limit(dx, dy, cfg.max_speed)
    steer_x, steer_y = (sx - vx), (sy - vy)
    return _limit(steer_x, steer_y, cfg.max_force)

def boids_step_accels_v1(
    positions: List[Vec2],
    velocities: List[Vec2],
    cfg: BoidsConfigV1,
) -> List[Vec2]:
    """
    Compute per-boid acceleration vectors from alignment/cohesion/separation.
    Deterministic, O(n^2), intended for small-medium swarms.
    """
    n = min(len(positions), len(velocities))
    accels: List[Vec2] = [(0.0, 0.0) for _ in range(n)]
    if n == 0:
        return accels

    nr2 = cfg.neighbor_radius * cfg.neighbor_radius
    sr2 = cfg.separation_radius * cfg.separation_radius

    for i in range(n):
        px, py = positions[i]
        vx, vy = velocities[i]

        align_x = align_y = 0.0
        coh_x = coh_y = 0.0
        sep_x = sep_y = 0.0
        count = 0

        for j in range(n):
            if j == i:
                continue
            qx, qy = positions[j]
            dx, dy = (qx - px), (qy - py)
            d2 = dx*dx + dy*dy
            if d2 > nr2:
                continue

            count += 1
            jvx, jvy = velocities[j]
            align_x += jvx
            align_y += jvy
            coh_x += qx
            coh_y += qy

            if d2 < sr2 and d2 > 1e-9:
                inv = 1.0 / math.sqrt(d2)
                # push away stronger when closer
                sep_x -= dx * inv
                sep_y -= dy * inv

        if count == 0:
            accels[i] = (0.0, 0.0)
            continue

        # Alignment: steer toward average heading
        align_x /= count
        align_y /= count
        ax, ay = _limit(align_x, align_y, cfg.max_speed)
        steer_align = _limit(ax - vx, ay - vy, cfg.max_force)

        # Cohesion: steer toward center of mass
        cx = coh_x / count
        cy = coh_y / count
        steer_coh = _seek(px, py, cx, cy, vx, vy, cfg)

        # Separation: steer away from close neighbors
        steer_sep = _limit(sep_x, sep_y, cfg.max_force)

        out_x = (
            steer_align[0] * cfg.w_alignment +
            steer_coh[0] * cfg.w_cohesion +
            steer_sep[0] * cfg.w_separation
        )
        out_y = (
            steer_align[1] * cfg.w_alignment +
            steer_coh[1] * cfg.w_cohesion +
            steer_sep[1] * cfg.w_separation
        )
        accels[i] = (out_x, out_y)

    return accels
