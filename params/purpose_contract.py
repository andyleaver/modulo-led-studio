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
        except Exception:
            params[s.key] = s.default
    return params
