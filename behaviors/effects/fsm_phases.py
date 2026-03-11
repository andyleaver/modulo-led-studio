from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

PHASE_COLOURS = [
    (255, 120, 80),
    (120, 220, 255),
    (190, 255, 120),
]

def _mix(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))

def _preview_emit(*, num_leds: int, params: dict, t: float, surface: dict | None = None, layout: dict | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    phase_len = max(2.0, float(params.get("phase_seconds", 6.0) or 6.0))
    phase_idx = int(t / phase_len) % len(PHASE_COLOURS)
    nxt_idx = (phase_idx + 1) % len(PHASE_COLOURS)
    local = (t % phase_len) / phase_len
    ease = 0.5 - 0.5 * math.cos(local * math.pi)
    c0 = PHASE_COLOURS[phase_idx]
    c1 = PHASE_COLOURS[nxt_idx]
    base = (_mix(c0[0], c1[0], ease), _mix(c0[1], c1[1], ease), _mix(c0[2], c1[2], ease))
    surface_cfg = canonical_surface_config(surface)
    w = int(surface_cfg.get("width") or n)
    h = int(surface_cfg.get("height") or 1)
    frame: List[RGB] = []
    for i in range(n):
        x = i % max(1, w)
        y = i // max(1, w)
        ripple = 0.65 + 0.35 * math.sin((x / max(1, w) + y / max(1, h)) * math.tau + t * 0.9)
        frame.append((int(base[0] * ripple), int(base[1] * ripple), int(base[2] * ripple)))
    return frame

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface_cfg = canonical_surface_config(surface)
    return ""

def register_fsm_phases():
    return register(
        BehaviorDef(
            "fsm_phases",
            title="FSM Phases",
            uses=["phase_seconds", "cpp"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
        )
    )
