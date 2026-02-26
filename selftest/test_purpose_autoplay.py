from __future__ import annotations
from behaviors.registry import get_behavior

def run():
    b = get_behavior("purpose_autoplay")
    assert b is not None
    st = b.state_init({"speed":1.0})
    st2 = b.state_tick(st, 0.016, {"speed":1.0})
    assert isinstance(st2, dict)
