from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.effects._export_hw import resolve_data_pin

RGB = Tuple[int, int, int]

def _clamp8(x: float) -> int:
    try:
        v = int(round(float(x)))
    except Exception:
        v = 0
    return 0 if v < 0 else (255 if v > 255 else v)

def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def _resolve_rgb(params: dict) -> RGB:
    color = params.get("color")
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        rgb = (_clamp8(color[0]), _clamp8(color[1]), _clamp8(color[2]))
    else:
        rgb = (
            _clamp8(params.get("r", 255)),
            _clamp8(params.get("g", 0)),
            _clamp8(params.get("b", 160)),
        )
    br = _clamp01(params.get("brightness", 1.0))
    return (_clamp8(rgb[0] * br), _clamp8(rgb[1] * br), _clamp8(rgb[2] * br))

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    px = _resolve_rgb(params or {})
    return [px] * max(1, int(num_leds))

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    rgb = _resolve_rgb(params or {})
    from export.arduino_exporter import make_solid_sketch
    return make_solid_sketch(
        num_leds=int((surface_cfg or {}).get("count", 1) or 1),
        led_pin=resolve_data_pin(surface_cfg),
        rgb=rgb,
    )

def register_solid_rgb_mix():
    return register(
        BehaviorDef(
            "solid_rgb_mix",
            title="1993 RGB Mix",
            uses=["color", "r", "g", "b", "brightness"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "1993 RGB Mix",
                "supports": "both",
                "supports_strip": True,
                "supports_matrix": True,
                "requires_audio": False,
                "shipped": True,
                "ui_category": "era",
            },
        )
    )
