from __future__ import annotations

from app.project_model import build_surface_dict

DEFAULT_PROJECT = {
    "schema_version": 21,
    "name": "New Project",
    "time": {
        "mode": "SIM_FIXED_DT",
        "fixed_dt": 0.0166666667,
        "paused": False,
        "seed": 1,
    },
    "spatial": {
        "enabled": True,
        "world_scale": 1.0,
        "origin": [0.0, 0.0],
        "rotation_deg": 0.0,
        "mirror_x": False,
        "mirror_y": False,
        "use_layout_coords": True,
    },
    "surface": build_surface_dict(kind="strip", count=144),
    "export": {
        "hw": {
            "data_pin": 6,
        },
    },
    "ui": {
        "target_mask": None,
        "era_complete": True,
        "era_template_applied": True,
    },
    "zones": [],
    "groups": [],
    "masks": {},
    "signals": {},
    "audio": {},
    "variables": {"number": {}, "toggle": {}},
    "rules": [],
    "layers": [],
}
