from __future__ import annotations

import copy
import uuid

from app.project_manager import DEFAULT_PROJECT


def build_red_hat_runner_project() -> dict:
    """Example: Red Hat Runner (state + rules).

    - 64x32 matrix defaults (serpentine OFF)
    - One stateful layer (red_hat_runner)
    - Rules v6 triggers jump on minute change (deterministic demo)
      and a small audio-energy boost can be enabled later.
    """

    proj = copy.deepcopy(DEFAULT_PROJECT)

    proj.setdefault("layout", {})
    proj["layout"]["shape"] = "matrix"
    proj["layout"]["mw"] = 64
    proj["layout"]["mh"] = 32
    proj["layout"]["width"] = 64
    proj["layout"]["height"] = 32
    proj["layout"]["serpentine"] = False
    proj["layout"]["matrix_serpentine"] = False
    proj["layout"]["flip_x"] = False
    proj["layout"]["matrix_flip_x"] = False
    proj["layout"]["flip_y"] = False
    proj["layout"]["matrix_flip_y"] = False
    proj["layout"]["rotate"] = 0
    proj["layout"]["matrix_rotate"] = 0

    uid = str(uuid.uuid4())
    layer = {
        "enabled": True,
        "uid": uid,
        "__uid": uid,
        "name": "Red Hat Runner",
        "behavior": "red_hat_runner",
        "opacity": 1.0,
        "blend_mode": "over",
        "target_kind": "all",
        "target_ref": 0,
        "params": {
            "speed": 1.0,
            "brightness": 1.0,
            "jump_now": 0.0,
            "gravity": 140.0,
            "jump_v": -70.0,
        },
        "modulotors": [],
    }

    proj["layers"] = [layer]

    # Rules: make him jump when the minute changes.
    proj["rules_v6"] = [
        {
            "id": "rh_clear",
            "enabled": True,
            "name": "00_clear_jump_now",
            "trigger": "tick",
            "when": {"signal": "audio.energy"},
            "action": {
                "kind": "set_layer_param",
                "layer": 0,
                "param": "jump_now",
                "expr": {"src": "const", "const": 0.0},
                "conflict": "last",
            },
        },
        {
            "id": "rh_min",
            "enabled": True,
            "name": "10_minute_jump",
            "trigger": "rising",
            "when": {"signal": "vars.number.clock.minute_changed"},
            "action": {
                "kind": "set_layer_param",
                "layer": 0,
                "param": "jump_now",
                "expr": {"src": "const", "const": 1.0},
                "conflict": "last",
            },
        },
    ]

    return proj
