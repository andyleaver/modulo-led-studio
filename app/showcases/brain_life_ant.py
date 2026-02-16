from __future__ import annotations

import copy
import uuid

from app.project_manager import DEFAULT_PROJECT


def build_brain_life_ant_project() -> dict:
    """Showcase: Brian's Brain + Game of Life + Langton's Ant (24x24 matrix).

    Purpose: demonstrate multiple independent evolving systems layered together.
    """
    proj = copy.deepcopy(DEFAULT_PROJECT)

    proj.setdefault("layout", {})
    proj["layout"]["shape"] = "cells"
    proj["layout"]["matrix_w"] = 24
    proj["layout"]["matrix_h"] = 24

    # Canonical mapping keys (Qt mapping UI)
    proj["layout"]["serpentine"] = False
    proj["layout"]["flip_x"] = False
    proj["layout"]["flip_y"] = False
    proj["layout"]["rotate"] = 0

    # Back-compat keys used by some code paths
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

    # Bottom: Brian's Brain (subtle moving field)
    brain = _mk_layer(
        "Brain",
        "brians_brain", {
            "color": [0, 180, 255]
        },
        opacity=0.25,
        blend_mode="over",
    )

    # Middle: Life (structure)
    life = _mk_layer(
        "Life",
        "game_of_life", {
            "color": [0, 255, 0]
        },
        opacity=0.35,
        blend_mode="over",
    )

    # Top: Ant (agent, very visible)
    ant = _mk_layer(
        "Ant",
        "langtons_ant", {
            "color": [255, 60, 0]
        },
        opacity=1.0,
        blend_mode="add",
    )

    proj["layers"] = [brain, life, ant]
    return proj
