from __future__ import annotations

"""write_the_loop: coder escape hatch.

Contract:
- Preview: user provides `py` which must define:
    def pixel(i, x, y, t, dt, seed, pf, audio, vars):
        return (r,g,b) as floats 0..1 or ints 0..255
- Export: user provides `cpp` which is injected into generated firmware as the body
  of a per-pixel function. It must set r,g,b as floats 0..1.

This is intentionally advanced: it is for coders who want to go beyond built-in behaviors
while keeping preview ⇢ export parity.
"""

from typing import List, Tuple, Any
import hashlib

from runtime.fsm_v1 import FSMV1, StateV1, TransitionV1, step_fsm_v1, make_phase_fsm_v1

RGB = Tuple[int, int, int]

_DEFAULT_PY = r"""
def pixel(i, x, y, t, dt, seed, pf, audio, vars):
    # Simple rainbow demo (export has a matching default)
    import math
    h = (x + t * 0.1) % 1.0
    s = 1.0
    v = 1.0
    k = (h * 6.0) % 6.0
    f = k - int(k)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    r = v * (1.0 - s * (1.0 - f))
    if int(k) == 0: rr,gg,bb = v,r,p
    elif int(k) == 1: rr,gg,bb = q,v,p
    elif int(k) == 2: rr,gg,bb = p,v,r
    elif int(k) == 3: rr,gg,bb = p,q,v
    elif int(k) == 4: rr,gg,bb = r,p,v
    else: rr,gg,bb = v,p,q
    return (rr,gg,bb)
""".strip()

_DEFAULT_CPP = r"""
// Rainbow demo (matches default Python preview)
float h = fmodf(x + t * 0.1f, 1.0f);
if (h < 0.0f) h += 1.0f;
const float s = 1.0f;
const float v = 1.0f;
float k = fmodf(h * 6.0f, 6.0f);
float f = k - floorf(k);
float p = v * (1.0f - s);
float q = v * (1.0f - s * f);
float rr = v * (1.0f - s * (1.0f - f));
int ki = (int)floorf(k);
if (ki == 0) { r = v; g = rr; b = p; }
else if (ki == 1) { r = q; g = v; b = p; }
else if (ki == 2) { r = p; g = v; b = rr; }
else if (ki == 3) { r = p; g = q; b = v; }
else if (ki == 4) { r = rr; g = p; b = v; }
else { r = v; g = p; b = q; }
""".strip()

def _coerce_rgb(v: Any) -> RGB:
    try:
        r,g,b = v
    except Exception:
        return (0,0,0)

    def to8(x: Any) -> int:
        try:
            xf = float(x)
        except Exception:
            return 0
        if xf <= 1.0:
            xf = max(0.0, min(1.0, xf)) * 255.0
        return int(max(0, min(255, round(xf))))

    return (to8(r), to8(g), to8(b))

class _CompiledScript:
    def __init__(self, src: str):
        self.src = src
        self.key = hashlib.sha256(src.encode("utf-8", errors="ignore")).hexdigest()[:12]
        self.func = None

    def compile(self):
        if self.func is not None:
            return
        safe_builtins = {"min": min, "max": max, "abs": abs, "int": int, "float": float, "range": range, "round": round}
        g = {"__builtins__": safe_builtins,
             "FSMV1": FSMV1, "StateV1": StateV1, "TransitionV1": TransitionV1,
             "step_fsm_v1": step_fsm_v1, "make_phase_fsm_v1": make_phase_fsm_v1}
        l: dict = {}
        code = compile(self.src, f"write_the_loop_{self.key}", "exec")
        exec(code, g, l)
        fn = l.get("pixel") or g.get("pixel")
        if not callable(fn):
            raise ValueError("write_the_loop: python script must define a callable pixel(...)")
        self.func = fn

    def pixel(self, *args):
        self.compile()
        return self.func(*args)

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None, **_kwargs) -> List[RGB]:
    p = params or {}
    script_py = str(p.get("py") or "").strip() or _DEFAULT_PY
    script = _CompiledScript(script_py)

    if state is None:
        state = {}
    vars0 = state.setdefault("vars", {})

    pf = [float(p.get("purpose_f0", 0.0) or 0.0),
          float(p.get("purpose_f1", 0.0) or 0.0),
          float(p.get("purpose_f2", 0.0) or 0.0),
          float(p.get("purpose_f3", 0.0) or 0.0)]

    w = int((layout or {}).get("mw") or (layout or {}).get("width") or 0) if isinstance(layout, dict) else 0
    h = int((layout or {}).get("mh") or (layout or {}).get("height") or 0) if isinstance(layout, dict) else 0
    is_matrix = (w > 1 and h > 1)

    seed = int(p.get("seed", 1337) or 1337)

    leds: List[RGB] = []
    for i in range(int(num_leds)):
        if is_matrix:
            x = 0.0 if w <= 1 else (float(i % w) / float(w - 1))
            y = 0.0 if h <= 1 else (float(i // w) / float(h - 1))
        else:
            x = 0.0 if num_leds <= 1 else (float(i) / float(num_leds - 1))
            y = 0.0
        try:
            out = script.pixel(i, x, y, float(t), float(dt), seed, pf, audio, vars0)
        except Exception:
            out = (0,0,0)
        leds.append(_coerce_rgb(out))
    return leds

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    return "// write_the_loop: export handled by layerstack exporter\n"

def default_params() -> dict:
    return {
        "seed": 1337,
        "py": _DEFAULT_PY,
        "cpp": _DEFAULT_CPP,
        "purpose_f0": 0.0,
        "purpose_f1": 0.0,
        "purpose_f2": 0.0,
        "purpose_f3": 0.0,
    }
