from __future__ import annotations

from typing import Any, Mapping


_CANONICAL_MAPPING_DEFAULTS = {
    "serpentine": False,
    "flip_x": False,
    "flip_y": False,
    "rotate": 0,
    "origin": "top_left",
}


def _coerce_mapping_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return bool(default)
    if isinstance(raw, (int, float)):
        try:
            return bool(int(raw))
        except Exception:
            return bool(default)
    try:
        s = str(raw).strip().lower()
    except Exception:
        return bool(default)
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off", ""):
        return False
    return bool(default)


def normalize_surface_mapping(mapping: Mapping[str, Any] | None = None, *, fallback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return canonical nested surface mapping.

    Canonical mapping truth lives under ``surface.mapping``. ``fallback`` allows
    older input shapes to be read without duplicating coercion rules.
    """
    nested = dict(mapping or {}) if isinstance(mapping, Mapping) else {}
    flat = fallback if isinstance(fallback, Mapping) else {}
    resolved: dict[str, Any] = {}
    for key, default in _CANONICAL_MAPPING_DEFAULTS.items():
        raw = nested.get(key, flat.get(key, default))
        if key in ('serpentine', 'flip_x', 'flip_y'):
            resolved[key] = _coerce_mapping_bool(raw, bool(default))
        elif key == 'rotate':
            try:
                rot = int(raw or 0) % 360
            except Exception:
                rot = 0
            resolved[key] = rot if rot in (0, 90, 180, 270) else 0
        else:
            origin = str(raw or 'top_left').strip().lower()
            resolved[key] = origin if origin in ('top_left', 'top_right', 'bottom_left', 'bottom_right') else 'top_left'
    return resolved


def normalize_surface_kind(raw: Any, *, default: str = "strip") -> str:
    kind = str(raw or default or 'strip').strip().lower()
    if kind == 'matrix':
        kind = 'cells'
    fallback = str(default or 'strip').strip().lower()
    if fallback == 'matrix':
        fallback = 'cells'
    return kind if kind in ('strip', 'cells') else (fallback if fallback in ('strip', 'cells') else 'strip')




def get_surface_kind_value(surface: Mapping[str, Any] | None = None, *, default: str = "strip", allow_shape_fallback: bool = True) -> str:
    """Return canonical surface kind from a surface-like mapping or object.

    ``kind`` carries intent. When only older shape-style input is present, this
    helper resolves it once so callers do not duplicate that logic. If geometry
    clearly describes cells, geometry wins over a stale strip marker.
    """
    raw = None
    used_shape_fallback = False
    width = None
    height = None
    if isinstance(surface, Mapping):
        raw = surface.get('kind')
        width = surface.get('width')
        height = surface.get('height')
        if raw in (None, '') and allow_shape_fallback:
            raw = surface.get('shape')
            used_shape_fallback = raw not in (None, '')
    elif surface is not None:
        try:
            raw = getattr(surface, 'kind', None)
        except Exception:
            raw = None
        try:
            width = getattr(surface, 'width', None)
        except Exception:
            width = None
        try:
            height = getattr(surface, 'height', None)
        except Exception:
            height = None
        if raw in (None, '') and allow_shape_fallback:
            try:
                raw = getattr(surface, 'shape', None)
                used_shape_fallback = raw not in (None, '')
            except Exception:
                raw = None
    kind = normalize_surface_kind(raw, default=default)
    try:
        w = int(width or 0)
    except Exception:
        w = 0
    try:
        h = int(height or 0)
    except Exception:
        h = 0
    if kind == 'strip' and w > 1 and h > 1:
        if used_shape_fallback or raw in (None, ''):
            return 'cells'
    return kind


def apply_surface_compat_mirrors(surface: Mapping[str, Any] | None = None, *, default_kind: str = "strip") -> dict[str, Any]:
    """Return canonical-only surface state.

    This helper normalizes to canonical ``kind`` + nested ``mapping`` and strips
    non-canonical mirror fields from the returned payload.
    """
    cfg = dict(surface or {}) if isinstance(surface, Mapping) else {}
    cfg['kind'] = get_surface_kind_value(cfg, default=default_kind)
    mapping = dict(get_surface_mapping_values(cfg))
    cfg.pop('shape', None)
    for key in tuple(_CANONICAL_MAPPING_DEFAULTS.keys()):
        cfg.pop(key, None)
    cfg['mapping'] = mapping
    return cfg

def canonical_surface_config(surface: Mapping[str, Any] | None = None, *, layout: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return one canonical surface config dict.

    Canonical callers should pass ``surface`` directly. ``layout`` is accepted so
    older call sites can still be normalized at the boundary. The returned dict is
    always a shallow copy so local mutation cannot leak back to stored state.

    Canonical surface truth is ``kind`` + nested ``mapping``. Older input forms may
    still be *read* at this boundary, but they are not mirrored back onto the
    returned live payload.
    """
    src = surface if isinstance(surface, Mapping) and surface else layout if isinstance(layout, Mapping) and layout else {}
    cfg = dict(src or {})
    kind = get_surface_kind_value(cfg, default='strip')
    mapping = get_surface_mapping_values(cfg)
    cfg['kind'] = kind
    cfg.pop('shape', None)
    for key in tuple(_CANONICAL_MAPPING_DEFAULTS.keys()):
        cfg.pop(key, None)
    cfg['mapping'] = dict(mapping)
    return cfg


def canonicalize_surface_geometry(surface: Mapping[str, Any] | None = None, *, layout: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return canonical surface config with normalized strip/cells geometry.

    This is the shared boundary for callers that need a fully materialized surface
    dict. It keeps ``kind`` as the intent-bearing field, preserves canonical nested
    mapping, strips mirror fields from the returned payload, and derives
    ``count``/``width``/``height`` through one shared path so
    preview/runtime/export/diagnostics do not drift.
    """
    cfg = canonical_surface_config(surface=surface, layout=layout)
    kind = get_surface_kind_value(
        cfg,
        default='cells' if int(cfg.get('width') or 0) > 0 and int(cfg.get('height') or 0) > 0 else 'strip',
    )
    cfg['kind'] = kind
    cfg.pop('shape', None)

    if kind == 'cells':
        try:
            width = max(1, int(cfg.get('width') or 1))
        except Exception:
            width = 1
        try:
            height = max(1, int(cfg.get('height') or 1))
        except Exception:
            height = 1
        cfg['width'] = int(width)
        cfg['height'] = int(height)
        cfg['count'] = int(width * height)
    else:
        try:
            count = max(1, int(cfg.get('count') or cfg.get('width') or 1))
        except Exception:
            count = 1
        cfg['count'] = int(count)
        cfg['width'] = int(count)
        cfg['height'] = 1
    return cfg


def resolve_surface_config(*, surface: Mapping[str, Any] | None = None, layout: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Wrapper for older imports; canonical callers should use canonical_surface_config()."""
    return canonical_surface_config(surface, layout=layout)


# Private alias kept for older internal imports.
_normalize_surface_kind = normalize_surface_kind


def get_surface_geometry_values(surface: Mapping[str, Any] | None = None, *, default_kind: str = "strip", default_count: int = 1) -> tuple[str, int, int, int]:
    """Return canonical kind/count/width/height for any surface-like mapping.

    This is the shared read boundary for callers that already hold a surface dict
    or snapshot and need canonical strip/cells geometry facts without
    re-implementing shape/kind/count/width/height coercion locally.
    """
    cfg = canonicalize_surface_geometry(surface=surface)
    kind = get_surface_kind_value(cfg, default=default_kind)
    try:
        count = max(1, int(cfg.get('count') or default_count or 1))
    except Exception:
        count = max(1, int(default_count or 1))
    try:
        width = max(1, int(cfg.get('width') or count or 1))
    except Exception:
        width = max(1, int(count or 1))
    try:
        height = max(1, int(cfg.get('height') or 1))
    except Exception:
        height = 1
    if kind == 'cells':
        count = max(1, int(width * height))
    else:
        width = max(1, int(count))
        height = 1
    return kind, int(count), int(width), int(height)


def get_default_surface_dict(*, kind: str = "strip", count: int = 144) -> dict[str, Any]:
    """Return canonical default surface dict.

    This keeps fallback/default surface authoring on the same core compatibility
    boundary used by live runtime/preview/export callers instead of re-building
    strip defaults ad hoc in multiple modules.
    """
    raw = {
        "kind": normalize_surface_kind(kind, default="strip"),
        "count": int(count or 1),
        "width": int(count or 1),
        "height": 1,
        "mapping": dict(_CANONICAL_MAPPING_DEFAULTS),
    }
    return canonicalize_surface_geometry(surface=raw)


def get_surface_mapping_values(surface: Mapping[str, Any] | None = None, *, fallback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return canonical mapping values for any surface-like mapping or object.

    Callers may pass a canonical surface dict, a compatibility surface/layout dict,
    or a ``SurfaceSpec``-style object carrying mapping fields as attributes. This
    keeps nested mapping reads on one shared boundary instead of rebuilding
    ``serpentine/flip_x/flip_y/rotate/origin`` locally.
    """
    nested = None
    flat: dict[str, Any] = {}

    if isinstance(surface, Mapping):
        nested = surface.get('mapping') if isinstance(surface.get('mapping'), Mapping) else None
        try:
            flat.update(dict(surface))
        except Exception:
            flat = {}
    elif surface is not None:
        try:
            maybe_mapping = getattr(surface, 'mapping', None)
        except Exception:
            maybe_mapping = None
        if isinstance(maybe_mapping, Mapping):
            nested = maybe_mapping
        else:
            nested = None
        for key in _CANONICAL_MAPPING_DEFAULTS:
            try:
                flat[key] = getattr(surface, key)
            except Exception:
                continue

    if isinstance(fallback, Mapping):
        try:
            flat.update(dict(fallback))
        except Exception:
            pass

    return normalize_surface_mapping(nested, fallback=flat)


def build_surface_geometry_dict(surface: Mapping[str, Any] | None = None, *, default_kind: str = "strip", default_count: int = 1) -> dict[str, Any]:
    """Return canonical surface geometry payload for live callers.

    Export/report/helper boundaries often need a materialized dict carrying
    canonical kind, width/height/count, and nested mapping truth. Compatibility
    mirror keys must not be re-emitted into live payloads here.
    """
    kind, count, width, height = get_surface_geometry_values(surface, default_kind=default_kind, default_count=default_count)
    mapping = get_surface_mapping_values(surface)
    payload = {
        "kind": kind,
        "width": int(width),
        "height": int(height),
        "count": int(count),
        "mapping": dict(mapping),
    }
    return canonicalize_surface_geometry(surface=payload)
