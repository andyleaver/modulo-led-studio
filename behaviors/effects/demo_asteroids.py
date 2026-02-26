from __future__ import annotations
SHIPPED = True

from behaviors.registry import BehaviorDef, register
from behaviors.effects.purpose_autoplay import _preview_emit as _pa_preview, _arduino_emit as _pa_arduino, USES as PA_USES

_DEFAULTS = {
    "brightness": 1.0,
    "speed": 1.25,
    "width": 0.22,
    "softness": 0.35,
    "purpose_f0": 1.0,
    "purpose_f1": 0.9,
    "purpose_f2": 0.35,
    "purpose_i0": 0
}

def _with_defaults(params: dict) -> dict:
    if params is None:
        params = {}
    # Do not mutate caller dict
    p = dict(params)
    for k, v in _DEFAULTS.items():
        if k not in p or p[k] is None:
            p[k] = v
            continue
        try:
            # If value is numerically zero, treat as "unset" for demo meters
            if isinstance(p[k], (int, float)) and float(p[k]) == 0.0:
                p[k] = v
        except Exception:
            pass
    return p

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None):
    return _pa_preview(num_leds=num_leds, params=_with_defaults(params), t=t, state=state)

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    return _pa_arduino(layout=layout, params=_with_defaults(params), ctx=ctx)

def register_demo_asteroids():
    defn = BehaviorDef(
        "demo_asteroids",
        title="Asteroids (Demo)",
        uses=list(PA_USES),
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    register(defn)

