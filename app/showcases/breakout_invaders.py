from __future__ import annotations

import copy
import uuid

from app.project_manager import DEFAULT_PROJECT


def build_breakout_invaders_project() -> dict:
    proj = copy.deepcopy(DEFAULT_PROJECT)
    proj.setdefault("layout", {})
    proj["layout"]["shape"] = "cells"
    proj["layout"]["matrix_w"] = 24
    proj["layout"]["matrix_h"] = 24
    proj["layout"]["serpentine"] = False
    proj["layout"]["flip_x"] = False
    proj["layout"]["flip_y"] = False
    proj["layout"]["rotate"] = 0
    proj["layout"]["matrix_serpentine"] = False
    proj["layout"]["matrix_flip_x"] = False
    proj["layout"]["matrix_flip_y"] = False
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

    breakout = _mk_layer(
        "Breakout",
        "breakout_game",
        {
            "moves_per_second": 30.0,
            "ball_free_ticks": 240,
            "top_gap_rows": 4,
            "brick_rows": 2,
            "max_block_health": 1,
            "retarget_teleport": 0,
            "preclear_nohit_thresh": 40,
        },
        opacity=0.9,
        blend_mode="over",
    )
    invaders = _mk_layer(
        "Invaders",
        "space_invaders_game",
        {
            "inv_moves_per_second": 6.0,
            "shots_per_second": 2.0,
            "inv_cols": 8,
            "inv_rows": 3,
        },
        opacity=0.75,
        blend_mode="add",
    )

    proj["layers"] = [breakout, invaders]
    return proj
