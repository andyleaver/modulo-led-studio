from __future__ import annotations
from typing import Dict, Any, List

from .registry import PARAMS

# Keys always present on every layer (mod targets even if effect doesn't explicitly use them)
ALWAYS_KEYS = ["purpose_f0","purpose_f1","purpose_f2","purpose_f3","purpose_i0","purpose_i1","purpose_i2","purpose_i3"]


def defaults_for(keys: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in list(keys) + ALWAYS_KEYS:
        if k in PARAMS:
            out[k] = PARAMS[k].get("default")
    return out

def ensure_params(params: Dict[str, Any] | None, keys: List[str]) -> Dict[str, Any]:
    """Return a params dict that contains at least defaults for given keys."""
    params = dict(params or {})
    for k in list(keys) + ALWAYS_KEYS:
        if k not in params and k in PARAMS:
            params[k] = PARAMS[k].get("default")
    return params
