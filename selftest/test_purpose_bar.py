from __future__ import annotations
from behaviors.registry import get_behavior
from purpose.contract import FLOAT_KEYS, INT_KEYS

def run():
    b = get_behavior("purpose_bar")
    assert b is not None
    # preview emit should not crash without explicit purpose keys
    frame = b.preview_emit(num_leds=60, params={"brightness":1.0,"speed":1.0}, t=0.0, state=None)
    assert isinstance(frame, list) and len(frame)==60
