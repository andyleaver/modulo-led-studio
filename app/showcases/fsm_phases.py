from __future__ import annotations

"""Showcase builder for the fsm_phases behavior.

Kept intentionally small and deterministic.
"""

from .new_era import _base_matrix_project, _mk_layer


def build_fsm_phases_project() -> dict:
    proj = _base_matrix_project(w=32, h=16)
    proj["layers"] = [
        _mk_layer(
            "FSM Phases",
            "fsm_phases",
            {
                # purpose_f0 is used as a global brightness scalar by the overlay
                "purpose_f0": 0.9,
            },
            opacity=1.0,
            blend_mode="over",
        )
    ]
    return proj
