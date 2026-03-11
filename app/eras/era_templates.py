from __future__ import annotations

from typing import Dict, Any

from app.project_canonical import apply_project_root
from app.project_model import build_surface_dict
from models.schema import CURRENT_SCHEMA_VERSION
from .era_history import get_eras, get_default_era_id, get_era, get_studio_tools_for_era

def _base_ui(era_id: str, complete: bool = False) -> Dict[str, Any]:
    era = get_era(str(era_id))
    phase_kind = str(getattr(getattr(era, 'gates', None), 'phase_kind', 'historical') or 'historical')
    return {
        'era_id': str(era_id),
        'era_complete': bool(complete),
        'era_template_applied': True,
        'era_done': {str(era_id): False},
        'era_mode': 'historical_progression',
        'era_phase_kind': phase_kind,
        'era_stop_here_ok': bool(getattr(getattr(era, 'gates', None), 'stop_here_ok', False)),
        'era_control_capabilities': list(getattr(getattr(era, 'gates', None), 'control_capabilities', []) or []),
        'era_studio_tools': list(get_studio_tools_for_era(era)),
        'studio_mode': 'effect_picker' if phase_kind == 'plateau' else ('full_modulo' if phase_kind == 'modulo' else 'historical'),
    }

def get_era_template_project(era_id: str) -> Dict[str, Any]:
    if not era_id:
        era_id = get_default_era_id()

    def layout_strip(n: int) -> Dict[str, Any]:
        return build_surface_dict(kind='strip', count=int(n))

    def layout_cells(w: int, h: int) -> Dict[str, Any]:
        return build_surface_dict(kind='cells', width=int(w), height=int(h))

    templates: Dict[str, Dict[str, Any]] = {
        'era_1962_red': {
            'name': 'Era — Single Indicator',
            'surface': layout_strip(1),
            'layers': [{'behavior': 'solid_red_1962', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_1972_yellow_green': {
            'name': 'Era — Multi-State Indicators',
            'surface': layout_strip(3),
            'layers': [{'behavior': 'solid_yellow_1972', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_1980s_high_brightness': {
            'name': 'Era — Programmed Alert Patterns',
            'surface': layout_strip(12),
            'layers': [{'behavior': 'pulse_red_1980s', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_1993_blue': {
            'name': 'Era — RGB Colour Mixing',
            'surface': layout_strip(12),
            'layers': [{'behavior': 'fade', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_1996_white': {
            'name': 'Era — White LED Lighting',
            'surface': layout_strip(12),
            'layers': [{'behavior': 'solid_white_1996', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_2000s_matrices': {
            'name': 'Era — Programmable Arrays',
            'surface': layout_cells(16, 8),
            'layers': [{'behavior': 'matrix_scroll_bar', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_2012_addressable': {
            'name': 'Era — Addressable Pixels',
            'surface': layout_strip(60),
            'layers': [{'behavior': 'color_wipe', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []}],
        },
        'era_usage_plateau': {
            'name': 'Modern LED App — Effect Picker',
            'surface': layout_strip(144),
            'layers': [
                {'behavior': 'chase', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'over', 'operators': []},
                {'behavior': 'color_wipe', 'enabled': True, 'opacity': 0.75, 'blend_mode': 'over', 'operators': []},
            ],
        },
        'era_now': {
            'name': 'Modulo — Full LED Control',
            'surface': layout_cells(32, 24),
            'layers': [
                {'behavior': 'memory_heatmap', 'enabled': True, 'opacity': 0.85, 'blend_mode': 'over', 'operators': []},
                {'behavior': 'boids_swarm', 'enabled': True, 'opacity': 1.0, 'blend_mode': 'add', 'operators': []},
                {'behavior': 'fsm_phases', 'enabled': True, 'opacity': 0.55, 'blend_mode': 'add', 'operators': []},
            ],
        },
    }

    base = templates.get(era_id) or templates.get(get_default_era_id(), {})
    p = dict(base)
    p.setdefault('schema_version', CURRENT_SCHEMA_VERSION)
    p.setdefault('masks', {})
    p.setdefault('zones', {})
    p.setdefault('groups', {})
    p.setdefault('signals', {})
    p.setdefault('variables', {})
    p.setdefault('rules', [])
    p.setdefault('spatial', {})
    p.setdefault('time', {})
    p.setdefault('audio', {'mode': 'sim'})
    p.setdefault('export', {'hw': {'data_pin': 6}})
    p, _validation, _changes = apply_project_root(p, 'ui', _base_ui(era_id, complete=False))
    return p

def get_all_template_ids() -> list[str]:
    return [e.era_id for e in get_eras()]
