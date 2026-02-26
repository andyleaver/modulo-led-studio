
from __future__ import annotations

"""
Force Particles core integration (v1)

This lifts the per-particle point-force integration and bounds interaction out of
behaviors/effects/force_particles.py so the simulation logic is reusable by
agents/particles/sprites without duplicating code.

- Deterministic: uses only provided inputs + callbacks for variable resolution.
- No rendering.
- No spawning.
"""

from typing import Callable, Dict, List, Tuple, Any
import math

def clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def integrate_point_forces_v1(
    *,
    parts: List[Dict[str, Any]],
    point_forces: List[Dict[str, Any]],
    params: Dict[str, Any],
    get_number: Callable[[str, float], float],
    get_toggle: Callable[[str, bool], bool],
    dt: float,
    w: int,
    h: int,
    spd: float,
    cx_center: float,
    cy_center: float,
    max_v: float = 25.0,
) -> Tuple[int, int, int, int]:
    """
    Returns (killed, wrap_count, wall_hit_count, bounds_exit_count)
    """
    killed = 0
    wrap_count = 0
    wall_hit_count = 0
    bounds_exit_count = 0

    # friction
    try:
        fr = float(params.get("friction", 0.0) or 0.0)
    except Exception:
        fr = 0.0
    if fr < 0.0:
        fr = 0.0

    # edge mode
    try:
        emode = str(params.get("edge_mode", "") or "").lower().strip()
    except Exception:
        emode = ""
    if not emode:
        emode = "wrap" if bool(params.get("wrap_edges", True)) else "bounce"

    for p in parts:
        try:
            x = float(p.get("x", 0.0))
            y = float(p.get("y", 0.0))
            vx = float(p.get("vx", 0.0))
            vy = float(p.get("vy", 0.0))
        except Exception:
            continue

        for f in point_forces:
            if not isinstance(f, dict):
                continue
            if not bool(f.get("enabled", True)):
                continue

            # enabled_var gate
            ev = str(f.get("enabled_var", "") or "").strip()
            if ev:
                try:
                    if not get_toggle(ev, False):
                        continue
                except Exception:
                    continue

            try:
                mode = str(f.get("mode", "attract") or "attract").lower().strip()
                strength = float(f.get("strength", 0.0) or 0.0) * float(spd)
            except Exception:
                continue

            # strength_var scaling
            sv = str(f.get("strength_var", "") or "").strip()
            if sv:
                try:
                    strength *= float(get_number(sv, 1.0))
                except Exception:
                    pass

            if mode in ("repel", "away", "push"):
                strength = -abs(strength)
            else:
                strength = abs(strength)

            src = str(f.get("source", "center") or "center").lower().strip()
            if src == "fixed":
                try:
                    fx = float(f.get("x", cx_center) or cx_center)
                except Exception:
                    fx = cx_center
                try:
                    fy = float(f.get("y", cy_center) or cy_center)
                except Exception:
                    fy = cy_center
                fx = clamp(fx, 0.0, float(max(0, w - 1)))
                fy = clamp(fy, 0.0, float(max(0, h - 1)))
            else:
                fx, fy = cx_center, cy_center

            dx = fx - x
            dy = fy - y
            dist2 = dx * dx + dy * dy
            if dist2 < 1e-6:
                dist2 = 1e-6
            dist = math.sqrt(dist2)

            # radius limit
            try:
                radius = float(f.get("radius", 0.0) or 0.0)
            except Exception:
                radius = 0.0
            rv = str(f.get("radius_var", "") or "").strip()
            if rv:
                try:
                    radius *= float(get_number(rv, 1.0))
                except Exception:
                    pass
            if radius > 0.0 and dist > radius:
                continue

            ux = dx / dist
            uy = dy / dist
            mag = strength / dist2
            mag = clamp(mag, -4.0, 4.0)
            vx += ux * mag
            vy += uy * mag

        # friction
        if fr > 0.0:
            damp = max(0.0, 1.0 - fr * dt)
            vx *= damp
            vy *= damp

        # clamp velocity
        vx = clamp(vx, -max_v, max_v)
        vy = clamp(vy, -max_v, max_v)

        # integrate position (legacy scale kept)
        x += vx * dt * 10.0
        y += vy * dt * 10.0

        # bounds
        if emode == "wrap":
            if w > 1:
                while x < 0.0:
                    x += float(w); wrap_count += 1
                while x >= float(w):
                    x -= float(w); wrap_count += 1
            else:
                x = 0.0
            if h > 1:
                while y < 0.0:
                    y += float(h); wrap_count += 1
                while y >= float(h):
                    y -= float(h); wrap_count += 1
            else:
                y = 0.0
        elif emode == "destroy":
            out = (x < 0.0) or (x > float(w - 1)) or (y < 0.0) or (y > float(h - 1))
            if out:
                bounds_exit_count += 1
                killed += 1
                try:
                    p["_kill"] = True
                except Exception:
                    pass
                continue
        else:
            # bounce
            if x < 0.0:
                x = 0.0; vx = abs(vx); wall_hit_count += 1
            if x > float(w - 1):
                x = float(w - 1); vx = -abs(vx); wall_hit_count += 1
            if y < 0.0:
                y = 0.0; vy = abs(vy); wall_hit_count += 1
            if y > float(h - 1):
                y = float(h - 1); vy = -abs(vy); wall_hit_count += 1

        p["x"], p["y"], p["vx"], p["vy"] = x, y, vx, vy

    return killed, wrap_count, wall_hit_count, bounds_exit_count
