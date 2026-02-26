from __future__ import annotations

import copy
import uuid

from app.project_manager import DEFAULT_PROJECT


def build_life_snake_project() -> dict:
    """Showcase: Life + Snake (matrix).

    - Forces matrix/cells layout with serpentine OFF.
    - Adds two layers:
        1) Game of Life (background)
        2) Snake (INO) overlay
    - Sets opacities/blend so both are visible immediately.
    """
    proj = copy.deepcopy(DEFAULT_PROJECT)

    # Force matrix layout + mapping defaults that read correctly for most panels.
    proj.setdefault("layout", {})
    proj["layout"]["shape"] = "cells"
    proj["layout"]["matrix_w"] = 16
    proj["layout"]["matrix_h"] = 16
    proj["layout"]["serpentine"] = False
    proj["layout"]["matrix_serpentine"] = False
    proj["layout"]["flip_x"] = False
    proj["layout"]["matrix_flip_x"] = False
    proj["layout"]["flip_y"] = False
    proj["layout"]["matrix_flip_y"] = False
    proj["layout"]["rotate"] = 0
    proj["layout"]["matrix_rotate"] = 0

    def _mk_layer(name: str, behavior: str, params: dict, *, opacity: float, blend_mode: str) -> dict:
        uid = str(uuid.uuid4())
        return {
            "enabled": True,
            "uid": uid,
            "__uid": uid,
            "name": name,
            "behavior": behavior,
            "opacity": float(opacity),
            "blend_mode": str(blend_mode),
            "target_kind": "all",
            "target_ref": 0,
            "params": dict(params or {}),
            "modulotors": [],
        }

    life = _mk_layer(
        "Life",
        "game_of_life",
        {},
        opacity=0.35,
        blend_mode="over",
    )
    snake = _mk_layer(
        "Snake",
        "snake_game_ino",
        {"snake_speed": 8.0},
        opacity=0.65,
        blend_mode="add",
    )

    proj["layers"] = [life, snake]
    return proj
