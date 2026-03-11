from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple
import math
import random

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

def _dims(surface: dict, n: int) -> tuple[int, int]:
    w = int((surface or {}).get("width") or n)
    h = int((surface or {}).get("height") or 1)
    if w * h != n:
        w = max(1, min(w, n))
        h = max(1, int(math.ceil(n / float(w))))
    return w, h

def _palette(v: float) -> RGB:
    v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
    if v < 0.33:
        t = v / 0.33
        return (int(10 + 40 * t), int(0 + 60 * t), int(20 + 100 * t))
    if v < 0.66:
        t = (v - 0.33) / 0.33
        return (int(50 + 150 * t), int(60 + 80 * t), int(120 - 70 * t))
    t = (v - 0.66) / 0.34
    return (int(200 + 55 * t), int(140 + 80 * t), int(50 * (1.0 - t)))

def _preview_emit(*, num_leds: int, params: dict, t: float, dt: float = 1.0 / 60.0, state: dict | None = None, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    state = state if isinstance(state, dict) else {}
    heat = state.get("heat")
    if not isinstance(heat, list) or len(heat) != n:
        heat = [0.0] * n
        state["heat"] = heat
        state["seed"] = int(params.get("seed", 1337) or 1337)
    rng = random.Random(int(state.get("seed", 1337)))
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    w, h = _dims(surface_cfg, n)
    decay = float(params.get("mem_decay", 0.985) or 0.985)
    decay = 0.80 if decay < 0.80 else (0.9999 if decay > 0.9999 else decay)
    inject = float(params.get("mem_inject", 0.35) or 0.35)
    radius = float(params.get("radius", 0.18) or 0.18)
    radius_px = max(1.0, radius * max(w, h))
    theta = float(state.get("theta", 0.0)) + float(dt) * (0.2 + float(params.get("speed", 0.35) or 0.35))
    state["theta"] = theta
    cx = (w - 1) * (0.5 + 0.33 * math.sin(theta * 0.9))
    cy = (h - 1) * (0.5 + 0.28 * math.cos(theta * 1.17))
    if rng.random() < 0.015:
        state["seed"] = int(state.get("seed", 1337)) + 1
    for i in range(n):
        heat[i] *= decay
    for y in range(h):
        for x in range(w):
            ii = y * w + x
            if ii >= n:
                continue
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            gain = math.exp(-d2 / (2.0 * radius_px * radius_px)) * inject
            heat[ii] = 1.0 if heat[ii] + gain > 1.0 else heat[ii] + gain
    return [_palette(v) for v in heat]

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_memory_heatmap():
    return register(
        BehaviorDef(
            "memory_heatmap",
            title="Memory Heatmap",
            uses=["mem_decay", "mem_inject", "radius", "speed", "seed"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
        )
    )
