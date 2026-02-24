from __future__ import annotations
from params.purpose_contract import ensure, clamp, FLOAT_KEYS, INT_KEYS

def run():
    p = {}
    ensure(p)
    for k in FLOAT_KEYS:
        assert k in p and 0.0 <= float(p[k]) <= 1.0
    for k in INT_KEYS:
        assert k in p and 0 <= int(p[k]) <= 255

    p["purpose_f0"] = 9.0
    p["purpose_i0"] = -5
    clamp(p)
    assert p["purpose_f0"] == 1.0
    assert p["purpose_i0"] == 0
