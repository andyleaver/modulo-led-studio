from __future__ import annotations
from typing import Dict, Any, List

from .registry import PARAMS
from .modulotors import Modulotor, apply_mod

def _clamp_param(key: str, v: Any):
    spec = PARAMS.get(key) or {}
    t = spec.get("type")

    if t == "float":
        try:
            v = float(v)
        except Exception:
            v = float(spec.get("default", 0.0))
        mn = spec.get("min", None)
        mx = spec.get("max", None)
        if mn is not None and v < float(mn):
            v = float(mn)
        if mx is not None and v > float(mx):
            v = float(mx)
        return v

    if t == "int":
        try:
            v = int(round(float(v)))
        except Exception:
            v = int(spec.get("default", 0))
        mn = spec.get("min", None)
        mx = spec.get("max", None)
        if mn is not None and v < int(mn):
            v = int(mn)
        if mx is not None and v > int(mx):
            v = int(mx)
        return v

    if t == "bool":
        try:
            return bool(v)
        except Exception:
            return bool(spec.get("default", False))

    if t == "enum":
        choices = list(spec.get("choices", []) or [])
        s = str(v) if v is not None else str(spec.get("default", ""))
        if choices and s not in choices:
            return str(spec.get("default", choices[0]))
        return s

    if t == "rgb":
        try:
            r,g,b = v
            return (int(r)&255, int(g)&255, int(b)&255)
        except Exception:
            d = spec.get("default", (0,0,0))
            return (int(d[0])&255, int(d[1])&255, int(d[2])&255)

    return v
    if t == "rgb":
        try:
            r,g,b = v
            return (int(r)&255, int(g)&255, int(b)&255)
        except Exception:
            d = spec.get("default", (0,0,0))
            return (int(d[0])&255, int(d[1])&255, int(d[2])&255)
    return v

def resolve(base_params: Dict[str, Any], t: float, *, audio=None, modulotors: List[Modulotor] | None = None) -> Dict[str, Any]:
    params = dict(base_params or {})
    modulotors = list(modulotors or [])

    for m in modulotors:
        tgt = (m.target or "").strip()
        if not tgt or tgt not in params:
            continue
        if PARAMS.get(tgt, {}).get("type") != "float":
            continue

        base = float(params.get(tgt, 0.0))
        sig = m.sample(float(t), audio=audio)
        newv = apply_mod(base, sig, m.mode, m.amount)
        params[tgt] = _clamp_param(tgt, newv)

    # final clamp pass
    for k in list(params.keys()):
        if k in PARAMS:
            params[k] = _clamp_param(k, params[k])
    return params
