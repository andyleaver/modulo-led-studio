from __future__ import annotations
SHIPPED = True

import math
from typing import Any, Dict, List, Tuple, Optional

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save
from behaviors.stateful_adapter import StatefulEffect, AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]
USES = ["preview", "arduino"]

# === Mechanical port of the FastLED+MSGEQ7 sketch (4th section) from 'game visuals.ino' ===

NUM_LEDS_DEFAULT = 575
NUM_BARS = 7

NOISE_FLOOR = 90
GAIN = 2.5

bandThreshold = [10, 15, 12, 24, 20, 20, 18]
bandSize = [75, 100, 75, 75, 75, 75, 75]

bandColor: List[RGB] = [
    (255, 0, 0),      # 0 Red (stereo bars)
    (255, 80, 0),     # 1 Orange (full-strip kick)
    (0, 180, 0),      # 2 Green (bottom main)
    (255, 255, 0),    # 3 Yellow (bottom overlay)
    (50, 0, 80),      # 4 Purple (top overlay)
    (0, 0, 255),      # 5 Blue (top main)
    (255, 255, 255),  # 6 White (peaks)
]

# Physical centers from INO
bottomMid = 468
topMid = 176
leftMid = 320
rightMid = 38

peakDecay = 6
peakThreshold = 20

def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)

def _scale8(i: int, scale_0_255: int) -> int:
    # Approximate FastLED scale8: (i * scale) / 255
    return (i * scale_0_255) // 255

def _nscale8(c: RGB, scale_0_255: int) -> RGB:
    s = _clamp(int(scale_0_255), 0, 255)
    return (_scale8(c[0], s), _scale8(c[1], s), _scale8(c[2], s))

def _lerp8(a: RGB, b: RGB, amount_0_255: int) -> RGB:
    # FastLED lerp8 toward b by amount
    t = _clamp(int(amount_0_255), 0, 255)
    return (
        a[0] + ((b[0] - a[0]) * t) // 255,
        a[1] + ((b[1] - a[1]) * t) // 255,
        a[2] + ((b[2] - a[2]) * t) // 255,
    )

def _audio_raw(v) -> int:
    """Accepts either 0..1 floats or 0..1023 ints."""
    try:
        x = float(v)
    except Exception:
        return 0
    if x <= 1.5:
        return _clamp(int(x * 1023.0), 0, 1023)
    return _clamp(int(x), 0, 1023)

def _map_int(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    if in_max == in_min:
        return int(out_min)
    t = (x - in_min) / (in_max - in_min)
    if t < 0: t = 0.0
    if t > 1: t = 1.0
    return int(out_min + t * (out_max - out_min))

class MSGEQ7ReactiveINO(StatefulEffect):
    """Mechanical translation of the INO drawing/math (including int conversions)."""

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", NUM_LEDS_DEFAULT) or NUM_LEDS_DEFAULT)
        seed = int(params.get("seed", 1)) & 0xFFFFFFFF
        state.clear()
        state["_n"] = n
        state["seed"] = seed

        state["L"] = [0] * NUM_BARS
        state["R"] = [0] * NUM_BARS
        state["smoothL"] = [0.0] * NUM_BARS
        state["smoothR"] = [0.0] * NUM_BARS

        state["kickImpulse"] = 0.0
        state["peak2"] = 0
        state["peak5"] = 0

        state["_millis"] = 0
        rng = rng_load(state, seed=seed)
        rng_save(state, rng)

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        # advance virtual millis by dt
        state["_millis"] = int(state.get("_millis", 0) or 0) + int(float(dt) * 1000.0)

        a = audio if isinstance(audio, dict) else {}
        L = [0] * NUM_BARS
        R = [0] * NUM_BARS
        for b in range(NUM_BARS):
            L[b] = _audio_raw(a.get(f"l{b}", a.get(f"mono{b}", 0.0)))
            R[b] = _audio_raw(a.get(f"r{b}", a.get(f"mono{b}", 0.0)))
        state["L"] = L
        state["R"] = R

        # kickImpulse update (as in drawKickFullStrip)
        rawKick = max(L[1], R[1]) - NOISE_FLOOR
        rawKick = max(0, rawKick)
        rawKick = _clamp(int(rawKick * GAIN), 0, 1023)
        if rawKick > 150:
            state["kickImpulse"] = float(rawKick)
        ki = float(state.get("kickImpulse", 0.0) or 0.0) * 0.6
        if ki < 20:
            ki = 0.0
        state["kickImpulse"] = ki

        # Peaks are updated in render() per bar call exactly like INO.

    # ===== INO bandLevelLeft/Right =====

    def _band_level_left(self, state: Dict[str, Any], b: int) -> int:
        v = max(0, int(state["L"][b]) - NOISE_FLOOR)
        if v < bandThreshold[b]:
            v = 0
        v = _clamp(int(v * GAIN), 0, 1023)
        smooth = float(state["smoothL"][b]) * 0.75 + float(v) * 0.25
        state["smoothL"][b] = smooth
        return _map_int(smooth, 0, 1023, 0, bandSize[b])

    def _band_level_right(self, state: Dict[str, Any], b: int) -> int:
        v = max(0, int(state["R"][b]) - NOISE_FLOOR)
        if v < bandThreshold[b]:
            v = 0
        v = _clamp(int(v * GAIN), 0, 1023)
        smooth = float(state["smoothR"][b]) * 0.75 + float(v) * 0.25
        state["smoothR"][b] = smooth
        return _map_int(smooth, 0, 1023, 0, bandSize[b])

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        # FastLED.clear() then barId init to 255 (not needed for preview visuals)
        leds: List[RGB] = [(0, 0, 0)] * n
        rng = rng_load(state, seed=int(state.get("seed", 1)))

        # --- drawKickFullStrip ---
        baseBrightness = 30
        punch = _map_int(float(state.get("kickImpulse", 0.0) or 0.0), 0, 1023, 0, 255)
        punch = _clamp(punch + baseBrightness, 0, 255)
        c = _nscale8(bandColor[1], punch)
        for i in range(n):
            leds[i] = c

        # --- drawBand0CentersWithPeaks ---
        leftLenL = self._band_level_left(state, 0)
        leftLenR = self._band_level_right(state, 0)
        rightLenL = self._band_level_left(state, 0)
        rightLenR = self._band_level_right(state, 0)

        band6Val = max(self._band_level_left(state, 6), self._band_level_right(state, 6))

        ms = int(state.get("_millis", 0) or 0)
        breath = 0.8 + 0.2 * math.sin(ms * 0.006)

        mids = [leftMid % n, rightMid % n]
        lens = [[leftLenL, leftLenR], [rightLenL, rightLenR]]

        for m in range(2):
            mid = mids[m]
            # left side
            for i in range(lens[m][0]):
                idx = (mid - i + n) % n
                scale_f = (150 + (i * 100) / max(1, lens[m][0])) * breath
                scale8 = int(scale_f) & 255  # uint8_t conversion quirk
                c0 = _nscale8(bandColor[0], scale8)
                leds[idx] = _lerp8(leds[idx], c0, 200)
            # right side
            for i in range(lens[m][1]):
                idx = (mid + i) % n
                scale_f = (150 + (i * 100) / max(1, lens[m][1])) * breath
                scale8 = int(scale_f) & 255
                c0 = _nscale8(bandColor[0], scale8)
                leds[idx] = _lerp8(leds[idx], c0, 200)

        # White peak flicker at ends for band0
        if band6Val > peakThreshold:
            flickerWidth = 3
            ends = [
                (leftMid - leftLenL + n) % n,
                (leftMid + leftLenR - 1 + n) % n,
                (rightMid - rightLenL + n) % n,
                (rightMid + rightLenR - 1 + n) % n,
            ]
            for i in range(flickerWidth):
                for j in range(0, 4, 2):
                    if int(rng.randrange(2)) == 1:
                        leds[(ends[j] + i) % n] = _lerp8(leds[(ends[j] + i) % n], bandColor[6], 128)
                        leds[(ends[j + 1] - i + n) % n] = _lerp8(leds[(ends[j + 1] - i + n) % n], bandColor[6], 128)

        # --- drawBarWithWhitePeakStereo(2, bottomMid, peak2) ---
        leds = self._draw_bar_with_white_peak_stereo(state, leds, rng, band=2, center=bottomMid, peak_key="peak2")

        # --- drawBarWithWhitePeakStereo(5, topMid, peak5) ---
        leds = self._draw_bar_with_white_peak_stereo(state, leds, rng, band=5, center=topMid, peak_key="peak5")

        rng_save(state, rng)
        return leds

    def _draw_bar_with_white_peak_stereo(self, state: Dict[str, Any], leds: List[RGB], rng, *, band: int, center: int, peak_key: str) -> List[RGB]:
        n = len(leds)
        lenL = self._band_level_left(state, band)
        lenR = self._band_level_right(state, band)

        band6Val = max(self._band_level_left(state, 6), self._band_level_right(state, 6))

        peakPos = int(state.get(peak_key, 0) or 0)
        if band6Val > peakThreshold:
            if band6Val > peakPos:
                peakPos = band6Val
        else:
            peakPos -= peakDecay
            if peakPos < 0:
                peakPos = 0
        state[peak_key] = peakPos

        baseColor = bandColor[band]

        if band == 2:
            yellowLevel = max(self._band_level_left(state, 3), self._band_level_right(state, 3))
            if yellowLevel > bandThreshold[3]:
                baseColor = bandColor[3]
        elif band == 5:
            purpleLevel = max(self._band_level_left(state, 4), self._band_level_right(state, 4))
            if purpleLevel > bandThreshold[4]:
                baseColor = bandColor[4]

        fadeWidth = 4
        ms = int(state.get("_millis", 0) or 0)
        breath = 0.75 + 0.25 * math.sin(ms * 0.004)

        center = center % n

        for i in range(lenL):
            idx = (center - i + n) % n
            color = baseColor
            if i >= lenL - fadeWidth:
                amt = (255 * (i - (lenL - fadeWidth))) // fadeWidth
                color = _lerp8(color, bandColor[1], amt)
            color = _nscale8(color, int(255 * breath) & 255)
            if 3 <= band <= 5:
                color = _nscale8(color, 150)
            leds[idx] = color

        for i in range(lenR):
            idx = (center + i) % n
            color = baseColor
            if i >= lenR - fadeWidth:
                amt = (255 * (i - (lenR - fadeWidth))) // fadeWidth
                color = _lerp8(color, bandColor[1], amt)
            color = _nscale8(color, int(255 * breath) & 255)
            if 3 <= band <= 5:
                color = _nscale8(color, 150)
            leds[idx] = color

        if band6Val > peakThreshold:
            flickerWidth = 3
            endLeft = (center - lenL + n) % n
            endRight = (center + lenR - 1 + n) % n
            for i in range(flickerWidth):
                if int(rng.randrange(2)) == 1:
                    leds[(endLeft + i) % n] = _lerp8(leds[(endLeft + i) % n], bandColor[6], 128)
                    leds[(endRight - i + n) % n] = _lerp8(leds[(endRight - i + n) % n], bandColor[6], 128)

        return leds

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("MSGEQ7 Reactive (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter.")


def register_msgeq7_reactive_ino():
    effect = MSGEQ7ReactiveINO()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=575, mw=0, mh=0, fixed_dt=1/60))
    defn = BehaviorDef(
        "msgeq7_reactive_ino",
        title="MSGEQ7 Reactive (INO Port)",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
