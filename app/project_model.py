"""Project model helpers.

This file provides a stable API for components to retrieve canonical models derived
from project JSON (without duplicating logic).

Primary API:
  get_surface_spec(project) -> SurfaceSpec
"""

from __future__ import annotations

from typing import Any, Optional

from core.surface_spec import SurfaceSpec, surface_spec_from_layout
from core.surface_compat import canonicalize_surface_geometry, get_default_surface_dict as core_get_default_surface_dict, get_surface_geometry_values as core_get_surface_geometry_values, get_surface_kind_value as core_get_surface_kind_value, get_surface_mapping_values as core_get_surface_mapping_values, normalize_surface_kind, normalize_surface_mapping
from runtime.resolver import resolve_address


def coerce_surface_kind(kind: Any, *, default: str = "strip") -> str:
    """Return canonical surface kind for authored/runtime surface paths."""
    try:
        value = str(kind or '').strip().lower()
    except Exception:
        value = ''
    if value == 'indicator':
        return 'indicator'
    fallback = str(default or 'strip').strip().lower()
    if fallback == 'indicator':
        fallback = 'strip'
    return normalize_surface_kind(value, default=fallback)


def build_surface_dict(*, kind: str = "strip", count: int = 144, width: int = 1, height: int = 1, mapping: dict | None = None, cell_size: int | None = None, extras: dict | None = None) -> dict:
    """Return a canonical authored surface dict.

    Canonical callers should author ``kind`` + nested ``mapping`` first. Legacy
    ``shape`` and flat mapping keys remain migration-only evidence and are not
    emitted back into live authored state.
    """
    k = coerce_surface_kind(kind, default='strip')

    base_mapping = {
        'serpentine': False,
        'flip_x': False,
        'flip_y': False,
        'rotate': 0,
        'origin': 'top_left',
    }
    if isinstance(mapping, dict):
        for key in tuple(base_mapping.keys()):
            if key in mapping:
                base_mapping[key] = mapping.get(key)

    raw_surface = {
        'kind': k,
        'count': int(count or 1),
        'width': int(width or 1),
        'height': int(height or 1),
        'mapping': dict(base_mapping),
    }
    surface = canonicalize_surface_geometry(surface=raw_surface)
    if cell_size is not None:
        try:
            cell = int(cell_size or 0)
        except Exception:
            cell = 0
        if cell > 0:
            surface['cell_size'] = int(cell)
            surface['cell'] = int(cell)
    if isinstance(extras, dict):
        for key, value in extras.items():
            if value is not None and key not in surface:
                surface[key] = value
    return surface


def get_default_surface_dict(*, kind: str = "strip", count: int = 144) -> dict:
    """Return the canonical default authored surface for fallback callers."""
    return core_get_default_surface_dict(kind=kind, count=count)


def build_surface_from_evidence(surface: Any = None, *, default_kind: str = "strip", default_count: int = 144) -> dict:
    """Rebuild a canonical authored surface dict from raw surface evidence.

    This is a compatibility-only boundary for callers that still need to recover
    from raw ``project.surface``-style payloads after a higher-level canonical
    helper failed. Canonical callers should prefer ``get_surface_snapshot(...)``
    or ``get_surface_runtime_snapshot(...)`` first.
    """
    raw_surface = dict(surface or {}) if isinstance(surface, dict) else {}

    try:
        canonical = canonicalize_surface_geometry(surface=raw_surface)
    except Exception:
        canonical = {}

    kind = coerce_surface_kind(core_get_surface_kind_value(canonical or raw_surface, default=default_kind), default=default_kind)
    try:
        count = int(canonical.get('count') or raw_surface.get('count') or raw_surface.get('width') or default_count)
    except Exception:
        count = int(default_count)
    try:
        width = int(canonical.get('width') or raw_surface.get('width') or count or 1)
    except Exception:
        width = max(1, int(count or 1))
    try:
        height = int(canonical.get('height') or raw_surface.get('height') or 1)
    except Exception:
        height = 1

    mapping = canonical.get('mapping') if isinstance(canonical.get('mapping'), dict) else raw_surface.get('mapping')
    mapping = dict(mapping) if isinstance(mapping, dict) else {}

    extras = {
        k: v for k, v in raw_surface.items()
        if k not in {'kind', 'shape', 'count', 'width', 'height', 'mapping', 'serpentine', 'flip_x', 'flip_y', 'rotate', 'origin', 'cell_size', 'cell'}
    }
    return build_surface_dict(
        kind=kind,
        count=count,
        width=width,
        height=height,
        mapping=mapping,
        cell_size=canonical.get('cell_size') or canonical.get('cell') or raw_surface.get('cell_size') or raw_surface.get('cell'),
        extras=extras,
    )

def get_raw_surface_evidence(project: Any) -> dict:
    """Return a shallow copy of authored raw surface evidence, if present.

    This is diagnostics/compatibility evidence only. Canonical geometry/mapping
    truth must still come from resolver-backed helpers.
    """
    try:
        if isinstance(project, dict):
            raw_surface = project.get('surface') if isinstance(project.get('surface'), dict) else None
        else:
            raw_surface = getattr(project, 'surface', None)
        if isinstance(raw_surface, dict):
            return dict(raw_surface)
    except Exception:
        pass
    return {}




def get_leaked_layout_evidence(project: Any) -> dict:
    """Return a shallow copy of leaked root layout evidence, if present.

    Canonical runtime truth must not come from the root ``layout`` mirror. This
    helper exists so diagnostics can inspect whether migration residue survived
    without teaching live callers to read layout-era state directly again.
    """
    try:
        if isinstance(project, dict):
            raw_layout = project.get('layout') if isinstance(project.get('layout'), dict) else None
        else:
            raw_layout = getattr(project, 'layout', None)
        if isinstance(raw_layout, dict):
            return dict(raw_layout)
    except Exception:
        pass
    return {}


def get_surface_evidence_bundle(project: Any) -> dict:
    """Return diagnostics-only authored surface evidence bundle.

    This keeps raw ``surface`` evidence and leaked root ``layout`` residue behind
    one helper boundary so diagnostics can inspect survival without reviving
    layout-era reads throughout the live stack.
    """
    return {
        'raw_surface': get_raw_surface_evidence(project),
        'leaked_layout': get_leaked_layout_evidence(project),
    }

def _merge_surface_runtime_extras(surface: dict | None, *sources: Any) -> dict:
    """Merge non-authoritative runtime/authored surface extras onto a snapshot."""
    merged = dict(surface or {}) if isinstance(surface, dict) else {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        try:
            if isinstance(source.get('coords'), list):
                merged['coords'] = list(source.get('coords') or [])
            if isinstance(source.get('exists_mask'), list):
                merged['exists_mask'] = list(source.get('exists_mask') or [])
            for key in ('cell_size', 'cell'):
                try:
                    value = int(source.get(key) or 0)
                except Exception:
                    value = 0
                if value > 0:
                    merged[key] = int(value)
        except Exception:
            continue
    return merged

def get_surface_snapshot(project: Any) -> dict:
    """Return canonical surface snapshot derived from resolver reads.

    Geometry + mapping truth must come from canonical addresses, never from raw
    legacy layout mirrors. Raw surface extras such as coords may still be carried
    through as non-authoritative evidence only.
    """
    defaults = {
        'project.surface.kind': 'strip',
        'project.surface.count': 144,
        'project.surface.width': 144,
        'project.surface.height': 1,
        'project.surface.mapping.serpentine': False,
        'project.surface.mapping.flip_x': False,
        'project.surface.mapping.flip_y': False,
        'project.surface.mapping.rotate': 0,
        'project.surface.mapping.origin': 'top_left',
    }
    snap = {}
    for addr, fallback in defaults.items():
        try:
            snap[addr] = resolve_address(project=project, address=addr, default=fallback).value
        except Exception:
            snap[addr] = fallback

    mapping = core_get_surface_mapping_values({
        'mapping': {
            'serpentine': snap['project.surface.mapping.serpentine'],
            'flip_x': snap['project.surface.mapping.flip_x'],
            'flip_y': snap['project.surface.mapping.flip_y'],
            'rotate': snap['project.surface.mapping.rotate'],
            'origin': snap['project.surface.mapping.origin'],
        }
    })

    kind, count, width, height = core_get_surface_geometry_values({
        'kind': snap.get('project.surface.kind'),
        'count': snap.get('project.surface.count'),
        'width': snap.get('project.surface.width'),
        'height': snap.get('project.surface.height'),
        'mapping': mapping,
    }, default_kind='strip', default_count=144)

    surface = build_surface_dict(
        kind=kind,
        count=count,
        width=width,
        height=height,
        mapping=mapping,
    )

    # Carry forward non-authoritative surface extras only. These must never
    # override the canonical geometry/mapping keys above. Hardware/export truth
    # does not belong on the layout snapshot and must not be mirrored here.
    return _merge_surface_runtime_extras(surface, get_raw_surface_evidence(project))



def get_surface_runtime_snapshot(project: Any, extra_surface: Any = None) -> dict:
    """Return canonical surface snapshot plus non-authoritative runtime extras.

    Geometry and mapping truth always come from ``get_surface_snapshot(...)``.
    Optional runtime-only extras such as ``coords`` / ``exists_mask`` / authored
    cell size may be merged in from an override surface dict for preview/runtime
    callers that carry transient geometry evidence alongside the project.
    """
    surface = dict(get_surface_snapshot(project) or {})
    return _merge_surface_runtime_extras(surface, get_raw_surface_evidence(project), extra_surface)



def apply_surface_dict_to_layout_model(layout_obj: Any, surface_cfg: dict | None) -> Any:
    """Apply a canonical surface dict to a model-style Layout object.

    This keeps model-backed probe/audit paths on the same canonical authored
    surface truth used by dict-based preview/export/diagnostics callers.
    """
    cfg = dict(surface_cfg or {}) if isinstance(surface_cfg, dict) else {}
    kind = coerce_surface_kind(cfg.get('kind'), default='strip')

    mapping = cfg.get('mapping') if isinstance(cfg.get('mapping'), dict) else {}
    try:
        setattr(layout_obj, 'kind', kind)
    except Exception:
        pass
    try:
        setattr(layout_obj, 'count', int(cfg.get('count') or 1))
    except Exception:
        pass
    try:
        setattr(layout_obj, 'width', int(cfg.get('width') or getattr(layout_obj, 'width', 1) or 1))
    except Exception:
        pass
    try:
        setattr(layout_obj, 'height', int(cfg.get('height') or getattr(layout_obj, 'height', 1) or 1))
    except Exception:
        pass

    cell_value = 0
    for key in ('cell_size', 'cell'):
        try:
            cell_value = int(cfg.get(key) or 0)
        except Exception:
            cell_value = 0
        if cell_value > 0:
            break
    if cell_value > 0:
        for key in ('cell_size', 'cell'):
            try:
                setattr(layout_obj, key, int(cell_value))
            except Exception:
                pass

    mapping_cfg = normalize_surface_mapping(mapping, fallback=cfg)
    for key in ('mapping',):
        try:
            setattr(layout_obj, key, dict(mapping_cfg))
        except Exception:
            pass
    for key in ('serpentine', 'flip_x', 'flip_y'):
        try:
            setattr(layout_obj, key, bool(mapping_cfg.get(key, False)))
        except Exception:
            pass
    try:
        setattr(layout_obj, 'rotate', int(mapping_cfg.get('rotate', 0) or 0))
    except Exception:
        pass
    try:
        setattr(layout_obj, 'origin', str(mapping_cfg.get('origin', 'top_left') or 'top_left'))
    except Exception:
        pass
    return layout_obj


def build_layout_model(project: Any):
    """Build a model-style Layout object from canonical project surface helpers."""
    from models.project import Layout

    snap = get_surface_snapshot(project)
    layout = Layout()
    return apply_surface_dict_to_layout_model(layout, snap)

def get_surface_layout_snapshot(project: Any) -> dict:
    """Compatibility wrapper for older callers.

    Canonical callers should use get_surface_snapshot(...).
    """
    return get_surface_snapshot(project)


def get_surface_spec(project: Any) -> Optional[SurfaceSpec]:
    """Return canonical SurfaceSpec for a project.

    Geometry/mapping truth is resolver-derived so every consumer (preview/export/
    diagnostics) reads the same canonical surface state.
    """
    try:
        return surface_spec_from_layout(get_surface_snapshot(project))
    except Exception:
        return None




def get_surface_geometry_values(surface: Any, *, default_kind: str = "strip", default_count: int = 1) -> tuple[str, int, int, int]:
    """Return canonical kind/count/width/height for any surface-like dict.

    This is the shared geometry read boundary for callers that already have a
    surface snapshot/evidence dict and need canonical geometry facts without
    reimplementing strip/cells coercion locally.
    """
    raw_surface = dict(surface or {}) if isinstance(surface, dict) else {}
    kind, count, width, height = core_get_surface_geometry_values(
        raw_surface,
        default_kind=default_kind,
        default_count=default_count,
    )
    return coerce_surface_kind(kind, default=default_kind), int(count), int(width), int(height)

def get_surface_kind(project: Any) -> str:
    """Return canonical surface kind ('strip' or 'cells')."""
    snap = get_surface_snapshot(project)
    return coerce_surface_kind((snap or {}).get('kind'), default='strip')


def get_surface_dimensions(project: Any) -> tuple[int, int]:
    """Return canonical surface width/height."""
    _kind, _count, width, height = get_surface_geometry_values(get_surface_snapshot(project) or {})
    return int(width), int(height)


def get_surface_count(project: Any) -> int:
    """Return canonical surface LED count."""
    _kind, count, _width, _height = get_surface_geometry_values(get_surface_snapshot(project) or {})
    return int(count)


def get_surface_mapping(project: Any) -> dict:
    """Return canonical nested surface mapping block."""
    snap = get_surface_snapshot(project) or {}
    mapping = snap.get('mapping') if isinstance(snap.get('mapping'), dict) else {}
    return normalize_surface_mapping(mapping)


def get_surface_cell_size(project: Any) -> int:
    """Return non-authoritative surface cell size used by preview/export widgets.

    Geometry truth still comes from canonical surface helpers. This helper only
    exposes the authored display cell size without forcing callers back onto raw
    project.surface reads.
    """
    snap = get_surface_snapshot(project) or {}
    for key in ('cell_size', 'cell'):
        try:
            value = int((snap or {}).get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            return int(value)
    return 14
