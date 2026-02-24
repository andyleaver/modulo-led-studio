from __future__ import annotations
SHIPPED = True

import math
import random
from typing import Dict, Any, List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save

RGB = Tuple[int,int,int]
USES = ["preview","arduino"]

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def _lerp(a: RGB, b: RGB, t: float) -> RGB:
    t = _clamp01(t)
    return (int(a[0] + (b[0]-a[0])*t)&255, int(a[1] + (b[1]-a[1])*t)&255, int(a[2] + (b[2]-a[2])*t)&255)

def _scale(c: RGB, s: float) -> RGB:
    s = _clamp01(s)
    return (int(c[0]*s)&255, int(c[1]*s)&255, int(c[2]*s)&255)

def _init_state(state: Dict[str, Any], n: int, seed: int):
    state.clear()
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["n"] = int(n)
    state["audio"] = {}
    state["smoothL"] = [0.0]*7
    state["smoothR"] = [0.0]*7
    state["kick"] = 0.0
    state["peak2"] = 0
    state["peak5"] = 0

def _get_audio(state: Dict[str, Any]) -> Dict[str, float]:
    a = state.get("audio")
    return a if isinstance(a, dict) else {}

def _band(state: Dict[str, Any], side: str, b: int) -> float:
    a = _get_audio(state)
    key = ("l" if side=="L" else "r") + str(int(b))
    try:
        return float(a.get(key, 0.0) or 0.0)
    except Exception:
        return 0.0

def _update(*, state: dict, params: dict, dt: float, t: float, audio=None):
    # audio is a flat dict energy, mono0.., l0.., r0..
    if isinstance(audio, dict):
        state["audio"] = dict(audio)

def _draw_kick(out: List[RGB], state: Dict[str, Any], *, base_brightness: float = 0.12):
    n = len(out)
    # kick uses band1 max(L,R)
    raw = max(_band(state,"L",1), _band(state,"R",1))
    # emphasize
    raw = _clamp01(raw*1.4)
    kick = float(state.get("kick", 0.0) or 0.0)
    if raw > 0.6:
        kick = raw
    kick *= 0.60
    if kick < 0.05: kick = 0.0
    state["kick"] = kick
    punch = _clamp01(base_brightness + kick)
    c = _scale((255,80,0), punch)  # orange
    for i in range(n):
        out[i] = c

def _bar_len(state: Dict[str, Any], band: int, side: str, size: int) -> int:
    # smooth
    v = _band(state, side, band)
    smooth = 0.25
    arr = state["smoothL"] if side=="L" else state["smoothR"]
    arr[band] = (1.0-smooth)*float(arr[band]) + smooth*float(v)
    vv = _clamp01(arr[band])
    return int(round(vv * size))

def _draw_center_bar(out: List[RGB], state: Dict[str, Any], *, band: int, center: int, base: RGB, overlay_band: int | None = None, overlay_color: RGB | None = None, dim: float = 1.0):
    n = len(out)
    size = 75 if band in (2,5) else 100
    lenL = _bar_len(state, band, "L", size)
    lenR = _bar_len(state, band, "R", size)

    # overlay replacement logic (like sketch)
    col = base
    if overlay_band is not None and overlay_color is not None:
        ov = max(_band(state,"L",overlay_band), _band(state,"R",overlay_band))
        if ov > 0.25:
            col = overlay_color

    # breathing
    breath = 0.75 + 0.25*math.sin(float(state.get("t",0.0))*0.004*1000.0)
    col = _scale(col, _clamp01(breath*dim))

    fade = 4
    # draw left
    for i in range(lenL):
        idx = (center - i) % n
        c = col
        if i >= lenL - fade and lenL > fade:
            c = _lerp(col, (255,80,0), (i-(lenL-fade))/fade)
        out[idx] = _lerp(out[idx], c, 0.8)
    # draw right
    for i in range(lenR):
        idx = (center + i) % n
        c = col
        if i >= lenR - fade and lenR > fade:
            c = _lerp(col, (255,80,0), (i-(lenR-fade))/fade)
        out[idx] = _lerp(out[idx], c, 0.8)

    # white peak flicker using band6
    peak = max(_band(state,"L",6), _band(state,"R",6))
    if peak > 0.35:
        rng = rng_load(state, seed=int(state.get('seed', 1337)))
        endL = (center - lenL) % n
        endR = (center + lenR - 1) % n
        for k in range(3):
            if rng.randrange(2) == 0:
                out[(endL + k) % n] = _lerp(out[(endL + k) % n], (255,255,255), 0.5)
                out[(endR - k) % n] = _lerp(out[(endR - k) % n], (255,255,255), 0.5)
        rng_save(state, rng)

def _draw_red_stereo_centers(out: List[RGB], state: Dict[str, Any], *, left_mid: int, right_mid: int):
    n = len(out)
    # band0 red stereo
    size = 75
    lL = _bar_len(state, 0, "L", size)
    lR = _bar_len(state, 0, "R", size)
    rL = lL
    rR = lR
    breath = 0.8 + 0.2*math.sin(float(state.get("t",0.0))*0.006*1000.0)

    def draw_mid(mid: int, lenL: int, lenR: int):
        for i in range(lenL):
            idx = (mid - i) % n
            c = _scale((255,0,0), _clamp01((150 + i*100/max(1,lenL))/255.0 * breath))
            out[idx] = _lerp(out[idx], c, 0.8)
        for i in range(lenR):
            idx = (mid + i) % n
            c = _scale((255,0,0), _clamp01((150 + i*100/max(1,lenR))/255.0 * breath))
            out[idx] = _lerp(out[idx], c, 0.8)

    draw_mid(left_mid, lL, lR)
    draw_mid(right_mid, rL, rR)

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None) -> List[RGB]:
    n = max(1, int(num_leds))
    if state is None or not isinstance(state, dict) or state.get("n") != n:
        seed = int(params.get("_seed", 2026) or 2026)
        state = {} if not isinstance(state, dict) else state
        _init_state(state, n, seed)

    state["t"] = float(t)

    out = [(0,0,0) for _ in range(n)]
    _draw_kick(out, state)

    # physical centers from sketch for 575; if n differs, scale proportionally
    def scale_pos(p: int, base: int) -> int:
        return int(round((p/float(base))*(n-1))) if base>1 else 0

    base_n = 575
    bottomMid = scale_pos(468, base_n)
    topMid    = scale_pos(176, base_n)
    leftMid   = scale_pos(320, base_n)
    rightMid  = scale_pos(38,  base_n)

    _draw_red_stereo_centers(out, state, left_mid=leftMid, right_mid=rightMid)

    # bottom: green main, yellow overlay from band3
    _draw_center_bar(out, state, band=2, center=bottomMid, base=(0,180,0), overlay_band=3, overlay_color=(255,255,0), dim=1.0)
    # top: blue main, purple overlay from band4 (dimmed a bit)
    _draw_center_bar(out, state, band=5, center=topMid, base=(0,0,255), overlay_band=4, overlay_color=(50,0,80), dim=0.6)

    return out

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    # Not yet integrated into the multi-layer Arduino emitter pipeline.
    return "// MSGEQ7 Visualizer now exports via layerstack exporter.\n"

def register_msgeq7_visualizer_575():
    bd = BehaviorDef(
        "msgeq7_visualizer_575",
        title="MSGEQ7 Visualizer (575)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    bd.update = _update
    return register(bd)
