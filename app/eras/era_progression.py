from __future__ import annotations

from typing import List
from app.eras.era_registry import ERAS
from app.project_canonical import apply_project_root

# Simple progression state stored in app_core.project["era_state"]
# This keeps the system deterministic and project-local.

def _state(project: dict) -> dict:
    p = project if isinstance(project, dict) else {}
    st0 = p.get("era_state")
    st = dict(st0) if isinstance(st0, dict) else {}
    changed = False
    if st.get("active_era") != ERAS[0].era_id:
        if "active_era" not in st:
            st["active_era"] = ERAS[0].era_id
            changed = True
    if not isinstance(st.get("unlocked"), list) or not st.get("unlocked"):
        st["unlocked"] = [ERAS[0].era_id]
        changed = True
    if changed or not isinstance(st0, dict):
        p2, _validation, _changes = apply_project_root(p, "era_state", st)
        if isinstance(project, dict):
            project.clear()
            project.update(p2)
        return dict((project if isinstance(project, dict) else p2).get("era_state") or {})
    return st

def get_active_era(project: dict) -> str:
    return _state(project)["active_era"]

def get_unlocked(project: dict) -> List[str]:
    return list(_state(project)["unlocked"])

def unlock_next(project: dict) -> str | None:
    st = _state(project)
    unlocked = list(st.get("unlocked") or [])
    for e in ERAS:
        if e.era_id not in unlocked:
            unlocked.append(e.era_id)
            st["active_era"] = e.era_id
            st["unlocked"] = unlocked
            p2, _validation, _changes = apply_project_root(project if isinstance(project, dict) else {}, "era_state", st)
            if isinstance(project, dict):
                project.clear()
                project.update(p2)
            return e.era_id
    return None

def set_active(project: dict, era_id: str):
    st = _state(project)
    if era_id in st["unlocked"]:
        st["active_era"] = era_id
        p2, _validation, _changes = apply_project_root(project if isinstance(project, dict) else {}, "era_state", st)
        if isinstance(project, dict):
            project.clear()
            project.update(p2)

def gates_for_project(project: dict) -> dict:
    era_id = get_active_era(project)
    for e in ERAS:
        if e.era_id == era_id:
            g = e.gates
            return {
                "allowed_effects": g.allowed_effects,
                "max_layers": g.max_layers,
                "allow_operators": g.allow_operators,
                "allow_rules": g.allow_rules,
                "allow_audio": g.allow_audio,
                "allow_targets": g.allow_targets,
                "allow_export": g.allow_export,
                "allow_matrix": g.allow_matrix,
                "allow_addressable": g.allow_addressable,
                "allow_presets": g.allow_presets,
                "allow_full_modulo": g.allow_full_modulo,
                "control_model": g.control_model,
                "phase_kind": g.phase_kind,
                "stop_here_ok": g.stop_here_ok,
            }
    return {}
