from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

FLOAT_KEYS = [f"purpose_f{i}" for i in range(4)]
INT_KEYS   = [f"purpose_i{i}" for i in range(4)]

@dataclass(frozen=True)
class PurposeSpec:
    key: str
    kind: str  # "float" or "int"
    default: float | int
    minv: float | int
    maxv: float | int

SPECS: List[PurposeSpec] = (
    [PurposeSpec(k, "float", 0.0, 0.0, 1.0) for k in FLOAT_KEYS] +
    [PurposeSpec(k, "int",   0,   0,   255) for k in INT_KEYS]
)

def ensure(params: Dict) -> Dict:
    if params is None:
        params = {}
    for s in SPECS:
        if s.key not in params:
            params[s.key] = s.default
    return params

def clamp(params: Dict) -> Dict:
    for s in SPECS:
        if s.key not in params:
            params[s.key] = s.default
        v = params.get(s.key, s.default)
        try:
            if s.kind == "float":
                fv = float(v)
                if fv < float(s.minv): fv = float(s.minv)
                if fv > float(s.maxv): fv = float(s.maxv)
                params[s.key] = fv
            else:
                iv = int(v)
                if iv < int(s.minv): iv = int(s.minv)
                if iv > int(s.maxv): iv = int(s.maxv)
                params[s.key] = iv
        except Exception as e:
            # Best-effort diagnostics once per key to avoid spam.
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                cache = globals().setdefault("_PURPOSE_CLAMP_ERR_CACHE", set())
                if s.key not in cache:
                    cache.add(s.key)
                    GLOBAL_DIAGS.exc(
                        domain="RUNTIME",
                        code="PURPOSE_PARAM_COERCE_FAILED",
                        summary="Purpose param could not be coerced; default applied",
                        details={"key": s.key, "value": v, "kind": s.kind},
                        exc=e,
                    )
            except Exception:
                pass
            params[s.key] = s.default
    return params
