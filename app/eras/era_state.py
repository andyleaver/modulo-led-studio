from __future__ import annotations

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

from typing import Dict, Any, List

from app.project_apply import replace_project_root
from .era_history import get_default_era_id, get_eras

LEGACY_ERA_ALIASES = {
    'era_1962_indicator': 'era_1962_red',
    'era_1970s_numeric_display': 'era_1972_yellow_green',
    'era_1980s_programmable_patterns': 'era_1980s_high_brightness',
    'era_1990s_rgb_mix': 'era_1993_blue',
    'era_2000s_microcontroller_arrays': 'era_2000s_matrices',
    'era_2011_addressable_pixels': 'era_2012_addressable',
    'era_effect_picker': 'era_usage_plateau',
    'era_modern_effect_picker': 'era_usage_plateau',
    'era_modulo_full': 'era_now',
    'era_full_modulo': 'era_now',
}

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="ERA_STATE_EXCEPTION", summary=where)
    except Exception:
        pass

def _ensure_ui(project: Dict[str, Any]) -> Dict[str, Any]:
    p = project if isinstance(project, dict) else {}
    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
    p = replace_project_root(p, 'ui', ui)
    return p

def _era_ids() -> List[str]:
    return [e.era_id for e in get_eras()]

def _normalize_era_id(era_id: str) -> str:
    val = str(era_id or '').strip()
    if not val:
        return get_default_era_id()
    return LEGACY_ERA_ALIASES.get(val, val)

def _default_done_map() -> Dict[str, bool]:
    return {e.era_id: False for e in get_eras()}

def ensure_era_in_project(project: Dict[str, Any]) -> Dict[str, Any]:
    p = _ensure_ui(project if isinstance(project, dict) else {})
    ui = p['ui']
    ids = _era_ids()
    default_id = get_default_era_id()

    era_id = _normalize_era_id(ui.get('era_id') or default_id)
    if era_id not in ids:
        era_id = default_id
    ui['era_id'] = era_id

    if 'era_complete' not in ui:
        ui['era_complete'] = False

    done = ui.get('era_done')
    if not isinstance(done, dict):
        done = {}
    merged = _default_done_map()
    for k, v in done.items():
        kk = _normalize_era_id(k)
        if kk in merged:
            merged[kk] = bool(v)
    ui['era_done'] = merged

    try:
        idx = ids.index(era_id)
    except Exception:
        idx = 0
    unlocked = ui.get('era_unlocked')
    if not isinstance(unlocked, list):
        unlocked = ids[: idx + 1]
    unlocked = [_normalize_era_id(x) for x in unlocked if _normalize_era_id(x) in ids]
    if era_id not in unlocked:
        unlocked = ids[: idx + 1]
    if not unlocked:
        unlocked = [default_id]
    ui['era_unlocked'] = unlocked
    p = replace_project_root(p, 'ui', ui)
    return p

def is_era_complete(project: Dict[str, Any]) -> bool:
    try:
        ui = (project.get('ui') or {})
        return bool(ui.get('era_complete', False)) if isinstance(ui, dict) else False
    except Exception as e:
        _diag_exc(e, 'app/eras/era_state.py')
        return False

def set_era_complete(project: Dict[str, Any], complete: bool) -> Dict[str, Any]:
    p = ensure_era_in_project(project)
    ui = p['ui']
    ui['era_complete'] = bool(complete)
    if bool(complete):
        final_id = _era_ids()[-1]
        ui['era_id'] = final_id
        ui['era_done'][final_id] = True
        ui['era_unlocked'] = _era_ids()
    p = replace_project_root(p, 'ui', ui)
    return p

def get_era_id(project: Dict[str, Any]) -> str:
    p = ensure_era_in_project(project)
    return str((p.get('ui') or {}).get('era_id') or get_default_era_id())

def set_era_id(project: Dict[str, Any], era_id: str) -> Dict[str, Any]:
    p = ensure_era_in_project(project)
    ui = p['ui']
    ids = _era_ids()
    target = _normalize_era_id(era_id)
    if target not in ids:
        target = get_default_era_id()
    unlocked = list(ui.get('era_unlocked') or [])
    if target not in unlocked:
        try:
            idx = ids.index(target)
            unlocked = ids[: idx + 1]
        except Exception:
            unlocked = [get_default_era_id()]
    ui['era_unlocked'] = unlocked
    ui['era_id'] = target
    p = replace_project_root(p, 'ui', ui)
    return p

def get_era_done_map(project: Dict[str, Any]) -> Dict[str, bool]:
    p = ensure_era_in_project(project)
    return dict(((p.get('ui') or {}).get('era_done') or {}))

def is_era_done(project: Dict[str, Any], era_id: str) -> bool:
    target = _normalize_era_id(era_id)
    return bool(get_era_done_map(project).get(target, False))

def get_unlocked_era_ids(project: Dict[str, Any]) -> List[str]:
    p = ensure_era_in_project(project)
    return list(((p.get('ui') or {}).get('era_unlocked') or []))

def unlock_era(project: Dict[str, Any], era_id: str) -> Dict[str, Any]:
    p = ensure_era_in_project(project)
    ui = p['ui']
    ids = _era_ids()
    target = _normalize_era_id(era_id)
    if target not in ids:
        return p
    unlocked = set(get_unlocked_era_ids(p))
    try:
        idx = ids.index(target)
        unlocked.update(ids[: idx + 1])
    except Exception:
        unlocked.add(target)
    ui['era_unlocked'] = [x for x in ids if x in unlocked]
    p = replace_project_root(p, 'ui', ui)
    return p

def mark_era_done(project: Dict[str, Any], era_id: str, done: bool = True) -> Dict[str, Any]:
    p = ensure_era_in_project(project)
    ui = p['ui']
    target = _normalize_era_id(era_id)
    done_map = dict(ui.get('era_done') or {})
    if target in done_map:
        done_map[target] = bool(done)
    ui['era_done'] = done_map
    if bool(done):
        p = unlock_era(p, target)
        nxt = get_next_era_id(p, target)
        if nxt:
            p = unlock_era(p, nxt)
            ui = p['ui']
    p = replace_project_root(p, 'ui', ui)
    return p

def get_next_era_id(project: Dict[str, Any], era_id: str | None = None) -> str | None:
    p = ensure_era_in_project(project)
    ids = _era_ids()
    current = _normalize_era_id(era_id or get_era_id(p))
    try:
        idx = ids.index(current)
    except Exception:
        return None
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return None
