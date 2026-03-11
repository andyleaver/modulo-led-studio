from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.effects._export_hw import resolve_data_pin

RGB = Tuple[int, int, int]

WHITE_PRESETS = {
    "warm": (255, 214, 170),
    "neutral": (255, 244, 229),
    "cool": (214, 235, 255),
}

def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def _resolve_rgb(params: dict) -> RGB:
    kind = str(params.get("white_type", "neutral") or "neutral").strip().lower()
    base = WHITE_PRESETS.get(kind, WHITE_PRESETS["neutral"])
    br = _clamp01(params.get("brightness", 1.0))
    return tuple(int(round(c * br)) for c in base)

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    px = _resolve_rgb(params or {})
    return [px] * max(1, int(num_leds))

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    from export.arduino_exporter import make_solid_sketch
    return make_solid_sketch(
        num_leds=int((surface_cfg or {}).get("count", 1) or 1),
        led_pin=resolve_data_pin(surface_cfg),
        rgb=_resolve_rgb(params or {}),
    )

def register_solid_white_1996():
    return register(
        BehaviorDef(
            "solid_white_1996",
            title="1996 White LED",
            uses=["white_type", "brightness"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "title": "1996 White LED",
                "supports": "both",
                "supports_strip": True,
                "supports_matrix": True,
                "requires_audio": False,
                "shipped": True,
                "ui_category": "era",
            },
        )
    )
