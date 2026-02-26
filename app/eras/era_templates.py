from __future__ import annotations

from typing import Dict, Any

from .era_history import get_eras, get_default_era_id


def _base_ui(era_id: str, complete: bool = False) -> Dict[str, Any]:
    return {
        "selected_layer": 0,
        "era_id": era_id,
        "era_complete": bool(complete),
    }


def get_era_template_project(era_id: str | None = None) -> Dict[str, Any]:
    """Return a real Modulo project dict that represents the *capabilities of the given era*.

    Notes:
    - These are real projects (normal schema), not a special demo mode.
    - We keep them tiny and auditable.
    - Behaviors used here must exist in code and be export-eligible where appropriate.
    """
    if not era_id:
        era_id = get_default_era_id()

    # Layout defaults: keep things simple and deterministic.
    def layout_strip(n: int) -> Dict[str, Any]:
        return {
            "type": "strip",
            "count": int(n),
            "num_leds": int(n),
            "led_pin": 6,
            "shape": "cells",
            "serpentine": False,
            "flip_x": False,
            "flip_y": False,
        }

    def layout_matrix(w: int, h: int) -> Dict[str, Any]:
        return {
            "type": "matrix",
            "width": int(w),
            "height": int(h),
            "matrix_w": int(w),
            "matrix_h": int(h),
            "mw": int(w),
            "mh": int(h),
            "shape": "cells",
            "serpentine": False,
            "matrix_serpentine": False,
            "matrix_flip_x": False,
            "matrix_flip_y": False,
        }

    # Era templates keyed by era_id from era_history.py
    # IMPORTANT: these reference shipped behaviors (code-truth).
    templates: Dict[str, Dict[str, Any]] = {
        # 1962 red indicator: 1 LED, on (solid red)
        "era_1962_red": {
            "name": "Era 0 — 1962 Indicator (Red)",
            "layout": layout_strip(1),
            "layers": [
                {"behavior": "solid_red_1962", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        # 1972 yellow: small cluster, static yellow
        "era_1972_yellow_green": {
            "name": "Era 1 — Discrete Color (Yellow)",
            "layout": layout_strip(5),
            "layers": [
                {"behavior": "solid_yellow_1972", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        # 1980s PWM pulse: shows brightness/time without full animation complexity
        "era_1980s_high_brightness": {
            "name": "Era 2 — Brightness & PWM (Pulse)",
            "layout": layout_strip(12),
            "layers": [
                {"behavior": "pulse_red_1980s", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        # RGB mixing: simple fade across RGB
        "era_rgb_1990s": {
            "name": "Era 3 — RGB Mixing",
            "layout": layout_strip(12),
            "layers": [
                {"behavior": "fade", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        
        # Early 1990s blue: demonstrate an explicit blue indicator using the general solid behavior.
        "era_1993_blue": {
            "name": "Era 4 — Efficient Blue",
            "layout": layout_strip(12),
            "layers": [
                {"behavior": "solid", "effect": "solid", "enabled": True, "opacity": 1.0, "blend_mode": "over",
                 "operators": [], "modulotors": [], "params": {"color": (0, 0, 255), "brightness": 1.0}}
            ],
        },
        # 1996 commercial white: phosphor-converted white (represented as a white indicator / lamp).
        "era_1996_white": {
            "name": "Era 5 — Commercial White",
            "layout": layout_strip(12),
            "layers": [
                {"behavior": "solid", "effect": "solid", "enabled": True, "opacity": 1.0, "blend_mode": "over",
                 "operators": [], "modulotors": [], "params": {"color": (255, 255, 255), "brightness": 1.0}}
            ],
        },

# Scanned displays: matrix-style visual (keep it simple: clock seconds dot is deterministic)
        "era_2000s_matrices": {
            "name": "Era 4 — Scanned Displays",
            "layout": layout_matrix(16, 16),
            "layers": [
                {"behavior": "clock_seconds_dot", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        # Addressable LEDs: classic chase
        "era_2012_addressable": {
            "name": "Era 5 — Addressable LEDs",
            "layout": layout_strip(60),
            "layers": [
                {"behavior": "chase", "enabled": True, "opacity": 1.0, "blend_mode": "over", "operators": []}
            ],
        },
        # Modulo era: system stack (exportable by default, as in your latest report)
        "era_modulo_now": {
            "name": "Era 6 — Modulo (What is possible now)",
            "layout": layout_matrix(32, 24),
            "layers": [
                {"behavior": "memory_heatmap", "enabled": True, "opacity": 0.85, "blend_mode": "over", "operators": []},
                {"behavior": "boids_swarm", "enabled": True, "opacity": 1.0, "blend_mode": "add", "operators": []},
                {"behavior": "fsm_phases", "enabled": True, "opacity": 0.55, "blend_mode": "add", "operators": []},
            ],
        },
    }

    base = templates.get(era_id)
    if base is None:
        # Fallback: use the first defined era template if an unknown id is provided.
        base = templates.get(get_default_era_id(), {})
    p = dict(base)
    p.setdefault("schema_version", 1)
    p.setdefault("masks", {})
    p.setdefault("zones", {})
    p.setdefault("groups", {})
    p.setdefault("signals", {})
    p.setdefault("variables", {})
    p.setdefault("rules_v6", [])
    p.setdefault("spatial_v1", {})
    p.setdefault("time_v1", {})
    p.setdefault("audio", {"mode": "sim"})
    p["ui"] = _base_ui(era_id, complete=False)
    return p


def get_all_template_ids() -> list[str]:
    # Keep stable order: era list order first, then any extras.
    ordered = [e.era_id for e in get_eras()]
    # Ensure templates cover every era; missing templates are allowed but will fallback.
    return ordered
