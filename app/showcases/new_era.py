from __future__ import annotations

import copy
import uuid

from app.project_manager import DEFAULT_PROJECT


def _base_matrix_project(*, w: int = 24, h: int = 24) -> dict:
    proj = copy.deepcopy(DEFAULT_PROJECT)
    proj.setdefault("layout", {})
    proj["layout"]["shape"] = "cells"
    proj["layout"]["matrix_w"] = int(w)
    proj["layout"]["matrix_h"] = int(h)
    proj["layout"]["serpentine"] = False
    proj["layout"]["matrix_serpentine"] = False
    proj["layout"]["flip_x"] = False
    proj["layout"]["matrix_flip_x"] = False
    proj["layout"]["flip_y"] = False
    proj["layout"]["matrix_flip_y"] = False
    proj["layout"]["rotate"] = 0
    proj["layout"]["matrix_rotate"] = 0
    return proj


def _mk_layer(name: str, behavior: str, params: dict, *, opacity: float = 1.0, blend_mode: str = "over") -> dict:
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


def build_boids_swarm_project() -> dict:
    proj = _base_matrix_project(w=32, h=24)
    proj["layers"] = [
        _mk_layer(
            "Boids",
            "boids_swarm",
            {"boids_count": 12, "boids_speed": 7.0, "boids_trail": 0.93},
            opacity=1.0,
            blend_mode="over",
        )
    ]
    return proj


def build_predator_prey_project() -> dict:
    proj = _base_matrix_project(w=24, h=24)
    proj["layers"] = [
        _mk_layer(
            "Predator/Prey",
            "predator_prey",
            {"pp_speed": 12.0, "pp_fear_radius": 7.0},
            opacity=1.0,
            blend_mode="over",
        )
    ]
    return proj


def build_memory_heatmap_project() -> dict:
    proj = _base_matrix_project(w=24, h=24)
    proj["layers"] = [
        _mk_layer(
            "Memory",
            "memory_heatmap",
            {"mem_decay": 0.985, "mem_inject": 0.35},
            opacity=1.0,
            blend_mode="over",
        )
    ]
    return proj


def build_ambient_dashboard_project() -> dict:
    proj = _base_matrix_project(w=32, h=16)
    proj["layers"] = [
        _mk_layer(
            "Dashboard",
            "ambient_dashboard",
            {"dash_pulse_hz": 1.2},
            opacity=1.0,
            blend_mode="over",
        )
    ]
    return proj


def build_agents_memory_narrative_project() -> dict:
    """Agents + long memory + narrative overlay.

    Preview-first because long-memory export wiring is still pending for this composite scene.
    """
    proj = _base_matrix_project(w=32, h=24)
    proj["layers"] = [
        _mk_layer(
            "Memory Heat",
            "memory_heatmap",
            {"mem_decay": 0.975, "mem_inject": 0.6, "mem_strip_width": 1.0},
            opacity=0.85,
            blend_mode="over",
        ),
        _mk_layer(
            "Boids",
            "boids_swarm",
            {"boids_count": 14, "boids_speed": 7.5, "boids_trail": 0.90},
            opacity=1.0,
            blend_mode="add",
        ),
        _mk_layer(
            "Narrative Overlay",
            "fsm_phases",
            {"purpose_f0": 0.75},
            opacity=0.55,
            blend_mode="add",
        ),
    ]
    return proj
