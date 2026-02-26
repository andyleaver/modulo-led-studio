from __future__ import annotations

from typing import Dict, Any

from .era_history import get_default_era_id


def ensure_era_in_project(project: Dict[str, Any]) -> Dict[str, Any]:
    p = project if isinstance(project, dict) else {}
    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
    if not ui.get('era_id'):
        ui['era_id'] = get_default_era_id()
    # Era onboarding completion flag. If False, the app boots into full-screen Era mode.
    if 'era_complete' not in ui:
        ui['era_complete'] = False

    # Once onboarding is complete, the project must run under the open "Now" gates.
    # Otherwise historical gating can block normal workflows (e.g. loading showcases).
    try:
        if bool(ui.get('era_complete', False)):
            if str(ui.get('era_id') or '').strip() != 'era_now':
                ui['era_id'] = 'era_now'
    except Exception:
        pass
    p['ui'] = ui
    return p


def is_era_complete(project: Dict[str, Any]) -> bool:
    try:
        ui = (project.get('ui') or {})
        if isinstance(ui, dict):
            return bool(ui.get('era_complete', False))
    except Exception:
        pass
    return False


def set_era_complete(project: Dict[str, Any], complete: bool) -> Dict[str, Any]:
    p = project if isinstance(project, dict) else {}
    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
    ui['era_complete'] = bool(complete)

    # Graduation: switch to open "Now" era gates.
    try:
        if bool(complete):
            ui['era_id'] = 'era_now'
    except Exception:
        pass
    p['ui'] = ui
    return p


def get_era_id(project: Dict[str, Any]) -> str:
    try:
        ui = (project.get('ui') or {})
        if isinstance(ui, dict):
            v = ui.get('era_id')
            if isinstance(v, str) and v.strip():
                return v.strip()
    except Exception:
        pass
    return get_default_era_id()


def set_era_id(project: Dict[str, Any], era_id: str) -> Dict[str, Any]:
    p = project if isinstance(project, dict) else {}
    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
    ui['era_id'] = str(era_id)
    p['ui'] = ui
    return p
