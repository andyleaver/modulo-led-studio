from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional
import math
import random

from behaviors.registry import BehaviorDef, register
from runtime.long_memory_v1 import LongMemory2D, LongMemory2DConfig

RGB = Tuple[int, int, int]
USES = ["mem_decay", "mem_inject", "mem_strip_width"]


def _clamp8(x: float) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))


def _dims(num_leds: int, params: Dict[str, Any]) -> Tuple[int, int]:
    mw = int(params.get("_mw", 0) or 0)
    mh = int(params.get("_mh", 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(num_leds):
        return mw, mh
    w = int(params.get("mem_strip_width", 32) or 32)
    if w < 1:
        w = 1
    h = max(1, int(num_leds) // w)
    if w * h < 1:
        return max(1, int(num_leds)), 1
    return w, h


def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    # Firmware implementation is embedded in the core exporter (beh_id == 20).
    # Exporter maps legacy params (mem_inject/mem_decay) into pf0/pf1.
    return ""


def _half_life_from_decay(decay: float, dt_ref: float = 1.0/60.0) -> float:
    """Convert legacy per-frame decay factor into an exponential half-life (seconds).

    Legacy behavior applied: value *= decay each tick (assuming ~60fps).
    We map that to exponential decay so LongMemory2D behaves similarly.
    """
    d = float(decay)
    if d <= 0.0:
        return 0.01
    if d >= 0.999999:
        return 1e9
    # d = 2^(-dt_ref/hl) => hl = -dt_ref*ln(2)/ln(d)
    import math
    return max(0.01, (-dt_ref * math.log(2.0)) / math.log(d))


class MemoryHeatmap:
    """A 'memory' field: events accumulate and decay over time.

    This is useful as a layer: it can store where motion/events happened.
    If audio is available, energy can increase injection rate.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 256) or 256)
        w, h = _dims(n, params)
        seed = int(params.get("seed", 777) or 777) & 0xFFFFFFFF
        rng = random.Random(seed)
        state.clear()
        state["w"] = int(w)
        state["h"] = int(h)
        mem = LongMemory2D(LongMemory2DConfig(width=w, height=h, half_life_s=_half_life_from_decay(float(params.get("mem_decay", 0.985) or 0.985))))
        state["_mem"] = mem
        state["heat"] = mem.buf  # alias for rendering/debug
        state["rng_seed"] = seed
        # a roaming injector point (like a cursor)
        state["p"] = [rng.random() * (w - 1 if w > 1 else 1), rng.random() * (h - 1 if h > 1 else 1)]

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)

        mem = state.get("_mem")
        if not isinstance(mem, LongMemory2D) or int(getattr(mem, "w", 0) or 0) != w or int(getattr(mem, "h", 0) or 0) != h:
            # (Re)create memory if missing or dims changed
            decay_legacy = float(params.get("mem_decay", 0.985) or 0.985)
            mem = LongMemory2D(LongMemory2DConfig(width=w, height=h, half_life_s=_half_life_from_decay(decay_legacy)))
            state["_mem"] = mem
            state["heat"] = mem.buf

        # Update half-life if user changed mem_decay
        decay_legacy = float(params.get("mem_decay", 0.985) or 0.985)
        decay_legacy = 0.80 if decay_legacy < 0.80 else (0.9999 if decay_legacy > 0.9999 else decay_legacy)
        hl = _half_life_from_decay(decay_legacy)
        if abs(float(mem.cfg.half_life_s) - float(hl)) > 1e-6:
            mem.cfg.half_life_s = float(hl)

        # Apply decay (dt-based)
        mem.step(float(dt))

        inject = float(params.get("mem_inject", 0.25) or 0.25)
        inject = 0.0 if inject < 0.0 else (2.0 if inject > 2.0 else inject)

        # audio boosts injection subtly
        if isinstance(audio, dict):
            e = float(audio.get("energy", 0.0) or 0.0)
            inject *= (1.0 + 1.5 * max(0.0, min(1.0, e)))

        # move injector point in a lissajous-ish path
        p = state.get("p")
        if not isinstance(p, list) or len(p) < 2:
            p = [0.0, 0.0]
            state["p"] = p
        px = float(p[0])
        py = float(p[1])
        px += math.cos(t * 0.9 + py * 0.03) * float(dt) * 8.0
        py += math.sin(t * 1.2 + px * 0.03) * float(dt) * 8.0
        # wrap
        if w > 0:
            px %= w
        if h > 0:
            py %= h
        p[0], p[1] = px, py

        # Reinforce at injector point
        mem.reinforce_points([(px, py)], amount=inject * 0.2, radius=0.0, wrap=True)

        # occasional random sparkles (memory of 'events')
        # rate ~ 2/sec, scaled by inject
        seed = int(state.get("rng_seed", 1) or 1) + int(t * 1000)
        rng = random.Random(seed)
        prob = float(dt) * 2.0 * min(2.0, max(0.2, inject))
        if rng.random() < prob:
            j = rng.randrange(0, w * h)
            x = j % w
            y = j // w
            mem.reinforce_points([(x, y)], amount=0.6, radius=0.0, wrap=True)


    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        mem = state.get("_mem")
        if isinstance(mem, LongMemory2D):
            heat = mem.buf
            state["heat"] = heat
        else:
            heat = state.get("heat")
        if not isinstance(heat, list) or len(heat) != w * h:
            heat = [0.0] * (w * h)
            state["heat"] = heat

        out: List[RGB] = [(0, 0, 0)] * n

        # palette: black -> blue -> magenta -> warm white
        for i in range(min(n, w * h)):
            v = float(heat[i] or 0.0)
            v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
            r = _clamp8(255.0 * (v ** 2.0))
            g = _clamp8(180.0 * (v ** 3.0))
            b = _clamp8(255.0 * (v ** 0.7))
            out[i] = (r, g, b)

        # draw injector point bright
        p = state.get("p")
        if isinstance(p, list) and len(p) >= 2:
            ix = int(round(float(p[0])))
            iy = int(round(float(p[1])))
            if ix < 0:
                ix = 0
            elif ix >= w:
                ix = w - 1
            if iy < 0:
                iy = 0
            elif iy >= h:
                iy = h - 1
            j = iy * w + ix
            if 0 <= j < n:
                out[j] = (255, 255, 255)

        return out


def _preview_emit(*, num_leds: int, params: dict, t: float, state: dict, dt: float, audio: Optional[dict] = None) -> List[RGB]:
    fx = MemoryHeatmap()
    if not state:
        fx.reset(state, params=params)
    fx.tick(state, params=params, dt=dt, t=t, audio=audio)
    return fx.render(num_leds=num_leds, params=params, t=t, state=state)


def register_memory_heatmap():
    bd = BehaviorDef(
        "memory_heatmap",
        title="Memory Heatmap",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    return register(bd)
