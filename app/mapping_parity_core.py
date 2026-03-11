from typing import Any, Dict, Tuple

from app.project_canonical import apply_project_root
from app.project_model import build_surface_dict, coerce_surface_kind, get_surface_snapshot, get_surface_kind, get_surface_mapping, get_surface_geometry_values
from preview.mapping import xy_index
from runtime.resolver_read import resolve_project_surface_field
from core.surface_compat import get_surface_kind_value, get_surface_mapping_values, normalize_surface_mapping


class ParityMismatch(Exception):
    pass


def surface_from_resolver(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return canonical surface facts from canonical resolver reads only."""
    width = int(resolve_project_surface_field(project=project, field='width', default=0).value or 0)
    height = int(resolve_project_surface_field(project=project, field='height', default=0).value or 0)
    count = int(resolve_project_surface_field(project=project, field='count', default=0).value or 0)
    kind = coerce_surface_kind(get_surface_kind(project) or resolve_project_surface_field(project=project, field='kind', default='strip').value, default='strip')
    mapping = get_surface_mapping(project)
    coords = (get_surface_snapshot(project) or {}).get('coords')
    surface = build_surface_dict(
        kind=kind,
        count=count,
        width=width,
        height=height,
        mapping=dict(mapping),
        extras={'coords': coords if isinstance(coords, list) else None},
    )
    return surface


def export_like_xy_index(surface: Dict[str, Any], x: int, y: int) -> int:
    """Return exporter-style XY index using canonical mapping truth.

    This intentionally keeps an export-local implementation so mapping parity can
    compare preview path logic against a separate export-like path instead of
    comparing a function to itself.
    """
    kind, count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
    mapping = get_surface_mapping_values(surface)
    if kind == 'strip':
        return export_strip_index(count, x)
    if width <= 0 or height <= 0:
        raise ParityMismatch('invalid cells dimensions')
    if not (0 <= x < width and 0 <= y < height):
        raise ParityMismatch('xy out of bounds')

    rot = mapping['rotate']
    origin = mapping['origin']
    flip_x = mapping['flip_x']
    flip_y = mapping['flip_y']
    serpentine = mapping['serpentine']

    xx = int(x)
    yy = int(y)
    if 'right' in origin:
        xx = width - 1 - xx
    if 'bottom' in origin:
        yy = height - 1 - yy

    if rot == 90:
        xx, yy = height - 1 - yy, xx
        width2, height2 = height, width
    elif rot == 180:
        xx, yy = width - 1 - xx, height - 1 - yy
        width2, height2 = width, height
    elif rot == 270:
        xx, yy = yy, width - 1 - xx
        width2, height2 = height, width
    else:
        width2, height2 = width, height

    if flip_x:
        xx = width2 - 1 - xx
    if flip_y:
        yy = height2 - 1 - yy

    xx = max(0, min(width2 - 1, xx))
    yy = max(0, min(height2 - 1, yy))
    if serpentine and (yy & 1):
        return int(yy * width2 + (width2 - 1 - xx))
    return int(yy * width2 + xx)


def export_strip_index(count: int, x: int) -> int:
    if count <= 0:
        raise ParityMismatch('invalid strip count')
    if not (0 <= x < count):
        raise ParityMismatch('strip index out of bounds')
    return x


def auto_step(total: int) -> int:
    if total <= 32:
        return 1
    if total <= 128:
        return 2
    if total <= 512:
        return 4
    return 8


def run_project_mapping_parity_probe(project: Dict[str, Any], mode: str = 'full') -> Dict[str, Any]:
    surface = surface_from_resolver(project)
    kind = get_surface_kind_value(surface, default='strip')
    mode = str(mode or 'full').strip().lower()
    if mode not in ('quick', 'full'):
        mode = 'full'

    if kind == 'strip':
        _kind, count, _width, _height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
        step = 1 if mode == 'full' else auto_step(count)
        mismatches = []
        checked = 0
        for x in range(0, count, step):
            checked += 1
            expected = export_strip_index(count, x)
            actual = x
            if expected != actual:
                mismatches.append({'x': x, 'expected': expected, 'actual': actual})
        return {
            'ok': not mismatches,
            'kind': kind,
            'mode': mode,
            'checked_points': checked,
            'mismatches': mismatches,
            'mapping': dict(get_surface_mapping_values(surface)),
        }

    _kind, _count, width, height = get_surface_geometry_values(surface, default_kind='strip', default_count=1)
    step_x = 1 if mode == 'full' else auto_step(width)
    step_y = 1 if mode == 'full' else auto_step(height)
    mismatches = []
    checked = 0
    mapping = get_surface_mapping_values(surface)
    for y in range(0, height, step_y):
        for x in range(0, width, step_x):
            checked += 1
            expected = export_like_xy_index(surface, x, y)
            actual = xy_index(
                x, y, width, height,
                serpentine=mapping['serpentine'],
                flip_x=mapping['flip_x'],
                flip_y=mapping['flip_y'],
                rotate=mapping['rotate'],
                origin=mapping['origin'],
            )
            if actual != expected:
                mismatches.append({'x': x, 'y': y, 'expected': expected, 'actual': actual})
    return {
        'ok': not mismatches,
        'kind': kind,
        'mode': mode,
        'checked_points': checked,
        'mismatches': mismatches,
        'mapping': dict(get_surface_mapping_values(surface)),
    }


def apply_surface_case(project: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    patched = dict(project)
    current = dict(get_surface_snapshot(patched) or {})
    incoming = dict(case or {}) if isinstance(case, dict) else {}
    kind = coerce_surface_kind(incoming.get('kind') or current.get('kind'), default='strip')
    mapping = dict(current.get('mapping') or {})
    if isinstance(incoming.get('mapping'), dict):
        mapping.update(incoming.get('mapping') or {})

    extras = {k: v for k, v in current.items() if k not in {'kind', 'shape', 'count', 'width', 'height', 'mapping', 'serpentine', 'flip_x', 'flip_y', 'rotate', 'origin', 'cell', 'cell_size'}}
    extras.update({k: v for k, v in incoming.items() if k not in {'kind', 'shape', 'count', 'width', 'height', 'mapping', 'serpentine', 'flip_x', 'flip_y', 'rotate', 'origin', 'cell', 'cell_size'}})

    surface = build_surface_dict(
        kind=kind,
        count=int(incoming.get('count') or current.get('count') or 1),
        width=int(incoming.get('width') or current.get('width') or 1),
        height=int(incoming.get('height') or current.get('height') or 1),
        mapping=mapping,
        cell_size=incoming.get('cell_size') or incoming.get('cell') or current.get('cell_size') or current.get('cell'),
        extras=extras,
    )
    patched2, _validation, _changes = apply_project_root(patched, 'surface', surface)
    return patched2
