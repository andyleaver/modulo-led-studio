from __future__ import annotations
from behaviors.registry import get_behavior

def run():
    b = get_behavior("asteroids_lite_purpose")
    assert b is not None
    st = b.state_init({"seed":1337})
    # run a few ticks
    for _ in range(10):
        st = b.state_tick(st, 1.0/60.0, {"speed":1.0,"density":0.6,"_num_leds":60})
        p = {}
        p = b.state_apply_to_params(p, st)
        assert 0.0 <= float(p.get("purpose_f0",0.0)) <= 1.0
