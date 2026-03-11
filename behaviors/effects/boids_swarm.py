from __future__ import annotations

from core.surface_compat import canonical_surface_config, get_surface_kind_value
SHIPPED = True

from typing import List, Tuple
import math
import random

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

def _dims(surface: dict, n: int, params: dict) -> tuple[int, int]:
    if get_surface_kind_value(surface, default="strip") == "strip":
        w = int(params.get("boids_strip_width", min(32, max(8, int(math.sqrt(n))))) or min(32, max(8, int(math.sqrt(n)))))
        w = max(1, min(w, n))
        h = max(1, int(math.ceil(n / float(w))))
    else:
        w = int((surface or {}).get("width") or max(1, int(math.sqrt(n))))
        h = int((surface or {}).get("height") or max(1, int(math.ceil(n / float(w)))))
    return max(1, w), max(1, h)

def _palette(i: int) -> RGB:
    cols = [(255, 120, 80), (120, 220, 255), (190, 255, 120), (255, 180, 240)]
    return cols[i % len(cols)]

def _preview_emit(*, num_leds: int, params: dict, t: float, dt: float = 1.0 / 60.0, state: dict | None = None, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    state = state if isinstance(state, dict) else {}
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    w, h = _dims(surface_cfg, n, params or {})
    count = max(3, min(24, int(params.get("boids_count", 10) or 10)))
    speed = float(params.get("boids_speed", 6.0) or 6.0)
    seed = int(params.get("seed", 4242) or 4242)
    agents = state.get("agents")
    if not isinstance(agents, list) or len(agents) != count:
        rng = random.Random(seed)
        agents = []
        for i in range(count):
            ang = rng.random() * math.tau
            agents.append({
                "x": rng.random() * (w - 1),
                "y": rng.random() * (h - 1),
                "vx": math.cos(ang),
                "vy": math.sin(ang),
                "c": _palette(i),
            })
        state["agents"] = agents
    cx = (w - 1) * (0.5 + 0.25 * math.sin(t * 0.21))
    cy = (h - 1) * (0.5 + 0.25 * math.cos(t * 0.17))
    for a in agents:
        dx = cx - a["x"]
        dy = cy - a["y"]
        d = max(0.001, math.hypot(dx, dy))
        a["vx"] = 0.94 * a["vx"] + 0.06 * (dx / d)
        a["vy"] = 0.94 * a["vy"] + 0.06 * (dy / d)
        norm = max(0.001, math.hypot(a["vx"], a["vy"]))
        a["vx"] /= norm
        a["vy"] /= norm
        step = float(dt) * speed
        a["x"] = (a["x"] + a["vx"] * step) % max(1.0, float(w))
        a["y"] = (a["y"] + a["vy"] * step) % max(1.0, float(h))
    frame = [(0, 0, 0)] * n
    for a in agents:
        x = int(round(a["x"])) % w
        y = int(round(a["y"])) % h
        ii = y * w + x
        if 0 <= ii < n:
            frame[ii] = a["c"]
    return frame

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_boids_swarm():
    return register(
        BehaviorDef(
            "boids_swarm",
            title="Boids Swarm",
            uses=["boids_count", "boids_speed", "boids_strip_width", "seed"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
        )
    )
