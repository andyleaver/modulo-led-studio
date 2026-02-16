from __future__ import annotations
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]


def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    """Fill all pixels with a single color scaled by `level`.

    Intended usage:
    - A Rules v6 tick rule routes `audio.energy` into params['level'].
    """
    n = max(1, int(num_leds))

    # Base RGB (defaults to a readable green)
    c = params.get("color", (0, 255, 0))
    try:
        r, g, b = int(c[0]) & 255, int(c[1]) & 255, int(c[2]) & 255
    except Exception:
        r, g, b = 0, 255, 0

    level = _clamp01(params.get("level", 0.15))
    # Optional shaping for visibility at low levels
    gamma = float(params.get("gamma", 1.8))
    try:
        level_shaped = level ** gamma
    except Exception:
        level_shaped = level

    rr = int(r * level_shaped) & 255
    gg = int(g * level_shaped) & 255
    bb = int(b * level_shaped) & 255
    px = (rr, gg, bb)
    return [px] * n


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Layerstack exporter handles this behavior; standalone emit not used.
    return ""


def register_audio_meter():
    return register(
        BehaviorDef(
            "audio_meter",
            title="Audio Meter (Preview Utility)",
            uses=["color", "level", "gamma"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
        )
    )
