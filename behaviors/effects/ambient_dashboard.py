from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]
USES = ["dash_pulse_hz", "dash_strip_width"]


def _clamp8(x: float) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))


def _dims(num_leds: int, params: Dict[str, Any]) -> Tuple[int, int]:
    mw = int(params.get("_mw", 0) or 0)
    mh = int(params.get("_mh", 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(num_leds):
        return mw, mh
    w = int(params.get("dash_strip_width", 48) or 48)
    if w < 1:
        w = 1
    h = max(1, int(num_leds) // w)
    if w * h < 1:
        return max(1, int(num_leds)), 1
    return w, h


def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Ambient Dashboard is preview-first (export wiring pending).")


class AmbientDashboard:
    """An ambient 'status wall' style visualization.

    No external data inputs required: it synthesizes a few stable "signals":
    - base mood gradient slowly shifts
    - three indicators pulse at different rates
    - optional audio energy can raise alert intensity

    This is meant as a *use-case* showcase: LEDs as an information surface.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        # stateless; keep a tiny accumulator for smoothing
        state.clear()
        state["alert"] = 0.0

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        alert = float(state.get("alert", 0.0) or 0.0)
        # audio energy can push alert up
        if isinstance(audio, dict):
            e = float(audio.get("energy", 0.0) or 0.0)
            alert = max(alert, min(1.0, e))
        # decay slowly
        alert *= 0.96
        state["alert"] = alert

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        w, h = _dims(n, params)

        out: List[RGB] = [(0, 0, 0)] * n

        # base mood gradient (blue-green) with slow hue shift
        phase = t * 0.12
        alert = float(state.get("alert", 0.0) or 0.0)

        def idx(x: int, y: int) -> int:
            return y * w + x

        for y in range(h):
            for x in range(w):
                i = idx(x, y)
                if i >= n:
                    break
                u = 0.0 if w <= 1 else float(x) / float(w - 1)
                v = 0.0 if h <= 1 else float(y) / float(h - 1)
                m = 0.5 + 0.5 * math.sin(phase + u * 2.2 + v * 1.7)

                # cool base
                r = 20 + 30 * m
                g = 40 + 110 * m
                b = 80 + 140 * (1.0 - m)

                # alert adds warm overlay
                r += 180.0 * alert
                g += 40.0 * alert
                b -= 60.0 * alert

                out[i] = (_clamp8(r), _clamp8(g), _clamp8(b))

        # three indicator "widgets" in corners
        # indicator 1: heartbeat
        hz = float(params.get("dash_pulse_hz", 1.0) or 1.0)
        hz = 0.1 if hz < 0.1 else (8.0 if hz > 8.0 else hz)
        hb = 0.5 + 0.5 * math.sin(t * math.tau * hz)
        hb2 = hb * hb

        def put(x: int, y: int, col: RGB) -> None:
            if 0 <= x < w and 0 <= y < h:
                j = idx(x, y)
                if 0 <= j < n:
                    out[j] = col

        put(0, 0, (_clamp8(255 * hb2), _clamp8(60 * hb2), _clamp8(60 * hb2)))
        put(w - 1, 0, (_clamp8(60 * hb2), _clamp8(255 * hb2), _clamp8(60 * hb2)))
        put(0, h - 1, (_clamp8(60 * hb2), _clamp8(60 * hb2), _clamp8(255 * hb2)))

        # top-right alert indicator
        a = min(1.0, max(0.0, alert))
        put(w - 1, h - 1, (_clamp8(255 * a), _clamp8(180 * a), 0))

        return out


def _preview_emit(*, num_leds: int, params: dict, t: float, state: dict, dt: float, audio: Optional[dict] = None) -> List[RGB]:
    fx = AmbientDashboard()
    if not state:
        fx.reset(state, params=params)
    fx.tick(state, params=params, dt=dt, t=t, audio=audio)
    return fx.render(num_leds=num_leds, params=params, t=t, state=state)


def register_ambient_dashboard():
    bd = BehaviorDef(
        "ambient_dashboard",
        title="Ambient Dashboard",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    return register(bd)
