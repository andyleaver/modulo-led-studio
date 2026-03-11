from app.project_canonical import canonicalize_project_dict
from app.project_model import build_surface_dict, coerce_surface_kind, get_surface_snapshot, get_surface_geometry_values
from typing import Any, Dict, List

from .mapping_parity_core import apply_surface_case, auto_step, export_like_xy_index, run_project_mapping_parity_probe, surface_from_resolver


def dump_surface_mapping(project: Dict[str, Any]) -> Dict[str, Any]:
    project2, _ = canonicalize_project_dict(project or {})
    surface = surface_from_resolver(project2)
    return {'surface': surface}


def run_project_mapping_pattern_probe(project: Dict[str, Any]) -> Dict[str, Any]:
    project2, _ = canonicalize_project_dict(project or {})
    surface = surface_from_resolver(project2)
    kind = coerce_surface_kind(surface.get('kind'), default='strip')
    points: List[Dict[str, int]] = []
    if kind == 'strip':
        _kind, count, _width, _height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
        step = auto_step(count)
        for x in range(0, count, step):
            points.append({'x': x, 'index': x})
    else:
        _kind, _count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
        step_x = auto_step(width)
        step_y = auto_step(height)
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                points.append({'x': x, 'y': y, 'index': export_like_xy_index(surface, x, y)})
    return {'surface': surface, 'points': points}


def run_project_mapping_parity_sweep(project: Dict[str, Any]) -> Dict[str, Any]:
    project2, _ = canonicalize_project_dict(project or {})
    surface = get_surface_snapshot(project2) if isinstance(project2, dict) else {}
    _base_kind, base_count, base_width, base_height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
    cases = [
        build_surface_dict(kind='strip', count=base_count),
        build_surface_dict(kind='cells', width=base_width, height=base_height, mapping={'serpentine': False, 'flip_x': False, 'flip_y': False, 'rotate': 0, 'origin': 'top_left'}),
        build_surface_dict(kind='cells', width=base_width, height=base_height, mapping={'serpentine': True, 'flip_x': False, 'flip_y': False, 'rotate': 0, 'origin': 'top_left'}),
        build_surface_dict(kind='cells', width=base_width, height=base_height, mapping={'serpentine': False, 'flip_x': True, 'flip_y': False, 'rotate': 90, 'origin': 'top_left'}),
        build_surface_dict(kind='cells', width=base_width, height=base_height, mapping={'serpentine': True, 'flip_x': False, 'flip_y': False, 'rotate': 0, 'origin': 'bottom_right'}),
    ]
    reports = []
    for case in cases:
        patched = apply_surface_case(project2, case)
        reports.append({'case': case, 'report': run_project_mapping_parity_probe(patched)})
    return {'cases': reports}




def run_project_mapping_parity_cases(project: Dict[str, Any]) -> Dict[str, Any]:
    sweep = run_project_mapping_parity_sweep(project)
    cases = []
    for item in sweep['cases']:
        report = item['report']
        cases.append({'case': item['case'], 'ok': bool(report.get('ok')), 'mismatch_count': len(report.get('mismatches') or [])})
    return {'cases': cases}


def run_project_mapping_parity_cells(project: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for callers using the cells naming."""
    return run_project_mapping_parity_cases(project)


def run_project_mapping_parity_matrix(project: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for callers using the matrix naming."""
    return run_project_mapping_parity_cases(project)
