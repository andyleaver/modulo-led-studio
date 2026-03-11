from __future__ import annotations

from typing import Any, Dict, Optional

from core.surface_compat import canonicalize_surface_geometry, get_default_surface_dict, get_surface_geometry_values, get_surface_kind_value, get_surface_mapping_values
from runtime.canonical_addr import ParsedAddress, canonical_registry, parse_canonical_address
from runtime.resolver_types import Resolved, _layer_dict, _layout_dict, _spatial_dict, _ui_dict, _audio_dict

def resolve_project_spatial_field(*, project: Any, field: str, default: Any = None) -> Resolved:
    field = str(field or '').strip()
    spatial = _spatial_dict(project)
    defaults = {
        'enabled': True,
        'world_scale': 1.0,
        'origin_x': 0.0,
        'origin_y': 0.0,
        'rotation_deg': 0.0,
        'mirror_x': False,
        'mirror_y': False,
        'use_layout_coords': True,
    }
    if default is not None:
        defaults[field] = default
    if not isinstance(spatial, dict):
        return Resolved(defaults.get(field), 'default')
    if field in ('enabled','mirror_x','mirror_y','use_layout_coords'):
        return Resolved(bool(spatial.get(field, defaults[field])), 'project' if field in spatial else 'default')
    if field in ('world_scale','rotation_deg'):
        try:
            return Resolved(float(spatial.get(field, defaults[field])), 'project' if field in spatial else 'default')
        except Exception:
            return Resolved(float(defaults[field]), 'default')
    if field in ('origin_x','origin_y'):
        origin = spatial.get('origin')
        idx = 0 if field.endswith('_x') else 1
        try:
            if isinstance(origin, (list, tuple)) and len(origin) >= 2:
                return Resolved(float(origin[idx]), 'project')
        except Exception:
            pass
        return Resolved(float(defaults[field]), 'default')
    return Resolved(defaults.get(field), 'default')

def resolve_system_state(*, project: Any, runtime: Optional[Dict[str, Any]] = None, key: str, default: Any = None) -> Resolved:
    key = str(key or '').strip()
    p = project if isinstance(project, dict) else {}
    systems = p.get('particle_systems') if isinstance(p.get('particle_systems'), dict) else {}
    if key == 'particles.total':
        total = 0
        for cfg in systems.values():
            if not isinstance(cfg, dict):
                continue
            state = cfg.get('state') if isinstance(cfg.get('state'), dict) else {}
            parts = state.get('particles') if isinstance(state.get('particles'), list) else []
            total += len(parts)
        return Resolved(total, 'project' if systems else 'default')
    if key.startswith('particles.'):
        parts = key.split('.')
        if len(parts) == 3:
            _scope, sys_name, field = parts
            cfg = systems.get(sys_name) if isinstance(systems, dict) else None
            if isinstance(cfg, dict):
                state = cfg.get('state') if isinstance(cfg.get('state'), dict) else {}
                if field == 'count':
                    plist = state.get('particles') if isinstance(state.get('particles'), list) else []
                    return Resolved(len(plist), 'project')
                if field == 'max_particles':
                    try:
                        return Resolved(int(state.get('max_particles', default if default is not None else 0)), 'project')
                    except Exception:
                        return Resolved(default, 'default')
    return Resolved(default, 'default')

def resolve_project_surface_field(*, project: Any, field: str, default: Any = None) -> Resolved:
    """Resolve canonical project.surface fields from canonical runtime schema only.

    Doctrine:
      - No legacy runtime surface keys.
      - Reads must not silently consume leaked root layout mirrors at runtime.
      - One-time migration on load may still rewrite old projects into canonical form.
      - Canonical mapping truth lives under project.surface.mapping.*.
        Flat surface mapping keys remain compatibility mirrors only.
    """
    field = str(field or '').strip()
    raw_authored_surface = None
    try:
        if isinstance(project, dict):
            maybe_surface = project.get('surface')
        else:
            maybe_surface = getattr(project, 'surface', None)
        if isinstance(maybe_surface, dict):
            raw_authored_surface = dict(maybe_surface)
    except Exception:
        raw_authored_surface = None

    canonical_surface = _layout_dict(project)

    _default_surface = get_default_surface_dict(kind='strip', count=144)
    _default_kind, _default_count, _default_width, _default_height = get_surface_geometry_values(
        _default_surface,
        default_kind='strip',
        default_count=144,
    )
    _default_mapping = get_surface_mapping_values(_default_surface)
    defaults = {
        'kind': _default_kind,
        'count': _default_count,
        'width': _default_width,
        'height': _default_height,
        'serpentine': _default_mapping.get('serpentine', False),
        'flip_x': _default_mapping.get('flip_x', False),
        'flip_y': _default_mapping.get('flip_y', False),
        'rotate': _default_mapping.get('rotate', 0),
        'origin': _default_mapping.get('origin', 'top_left'),
    }
    if default is not None:
        defaults[field] = default

    if not isinstance(canonical_surface, dict):
        return Resolved(defaults.get(field), 'default')

    authored_layout = dict(raw_authored_surface) if isinstance(raw_authored_surface, dict) else {}
    surface_evidence = authored_layout or canonical_surface
    if not surface_evidence:
        if field == 'mapping':
            return Resolved(get_surface_mapping_values({'mapping': defaults}), 'default')
        return Resolved(defaults.get(field), 'default')

    resolved_surface = canonicalize_surface_geometry(surface=surface_evidence) if isinstance(surface_evidence, dict) else {}
    kind = get_surface_kind_value(resolved_surface, default='strip')
    mapping = resolved_surface.get('mapping') if isinstance(resolved_surface.get('mapping'), dict) else {}

    def _mapping_value(key: str):
        raw_mapping = authored_layout.get('mapping') if isinstance(authored_layout.get('mapping'), dict) else {}
        if key in raw_mapping:
            return raw_mapping.get(key), 'project'
        if key in authored_layout:
            return authored_layout.get(key), 'compat'
        return defaults[key], 'default'

    def _resolved_mapping() -> tuple[dict, str]:
        raw = {}
        source = 'default'
        for key in ('serpentine', 'flip_x', 'flip_y', 'rotate', 'origin'):
            value, src = _mapping_value(key)
            raw[key] = value
            if src == 'project':
                source = 'project'
            elif src == 'compat' and source == 'default':
                source = 'compat'
        return get_surface_mapping_values({'mapping': raw}), source

    if field == 'mapping':
        resolved, source = _resolved_mapping()
        return Resolved(resolved, source)

    if field == 'kind':
        if 'kind' in authored_layout:
            source = 'project'
        elif 'shape' in authored_layout:
            source = 'compat'
        elif any(key in authored_layout for key in ('count', 'width', 'height')):
            source = 'project'
        else:
            source = 'default'
        return Resolved(kind, source)

    resolved_mapping, resolved_mapping_source = _resolved_mapping()

    kind, count, width, height = get_surface_geometry_values(resolved_surface, default_kind='strip', default_count=defaults['count'])

    if field in ('width', 'height', 'count'):
        has_kind = 'kind' in authored_layout
        has_shape = 'shape' in authored_layout
        has_count = 'count' in authored_layout
        has_width = 'width' in authored_layout
        has_height = 'height' in authored_layout

        if field == 'count':
            if has_count or (kind == 'strip' and has_width):
                source = 'project'
            elif has_shape and not has_kind:
                source = 'compat'
            else:
                source = 'default'
        elif field == 'width':
            if has_width or (kind == 'strip' and has_count):
                source = 'project'
            elif has_shape and not has_kind:
                source = 'compat'
            else:
                source = 'default'
        else:  # height
            if has_height:
                source = 'project'
            elif has_shape and not has_kind:
                source = 'compat'
            elif has_kind or has_count or has_width:
                source = 'project'
            else:
                source = 'default'

        return Resolved({'width': width, 'height': height, 'count': count}[field], source)
    if field == 'mapping':
        return Resolved(resolved_mapping, resolved_mapping_source)
    if field in ('serpentine', 'flip_x', 'flip_y', 'rotate', 'origin'):
        return Resolved(resolved_mapping[field], resolved_mapping_source)
    return Resolved(defaults.get(field), 'default')

def resolve_layer_field(
    *,
    project: Any,
    layer_index: int,
    field: str,
    runtime: Optional[Dict[str, Any]] = None,
    default: Any = None,
) -> Resolved:
    field = str(field or "").strip()
    i = int(layer_index)

    # 1) Operator overrides (future: route via canonical addresses).
    # For now, only composition fields are resolved here, so we don't consult _op_overrides.

    # 2) Runtime overrides (Rules/Modulators) - canonical keys only
    try:
        if isinstance(runtime, dict):
            lf = runtime.get("layer_fields")
            if isinstance(lf, list) and 0 <= i < len(lf):
                row = lf[i]
                if isinstance(row, dict) and field in row and row[field] is not None:
                    return Resolved(row[field], "runtime")
    except Exception:
        pass

    # 3) Authored project value
    L = _layer_dict(project, i)
    if isinstance(L, dict) and field in L and L[field] is not None:
        return Resolved(L[field], "project")

    # 4) Defaults
    if default is None:
        if field == "enabled":
            default = True
        elif field == "opacity":
            default = 1.0
        elif field == "blend_mode":
            default = "over"
        elif field == "order":
            default = i
    return Resolved(default, "default")

def resolve_project_postfx(
    *,
    project: Any,
    runtime: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """Return effective project-level postfx dict and its source mix.

    Source string:
      - 'runtime+project' if runtime overrides are applied
      - 'project' if only authored postfx exists
      - 'runtime' if only runtime overrides exist
      - 'default' if neither exists
    """
    base: Dict[str, Any] = {}
    rt: Dict[str, Any] = {}
    try:
        pf = getattr(project, "postfx", None)
        if isinstance(pf, dict):
            base = dict(pf)
    except Exception:
        pass
    try:
        if not base and isinstance(project, dict):
            pf = project.get("postfx")
            if isinstance(pf, dict):
                base = dict(pf)
    except Exception:
        pass
    try:
        if isinstance(runtime, dict):
            rtp = runtime.get("postfx")
            if isinstance(rtp, dict):
                rt = dict(rtp)
    except Exception:
        rt = {}

    if base and rt:
        base.update(rt)
        return base, "runtime+project"
    if base:
        return base, "project"
    if rt:
        return rt, "runtime"
    return {}, "default"

def resolve_project_variable(*, project: Any, runtime: Optional[Dict[str, Any]] = None, key: str, default: Any = None) -> Resolved:
    vkey = str(key or '').strip()
    if not vkey or '.' not in vkey:
        return Resolved(default, 'default')
    kind, name = vkey.split('.', 1)
    if not name:
        return Resolved(default, 'default')

    if isinstance(runtime, dict):
        rv = runtime.get('variables')
        if isinstance(rv, dict):
            bucket = rv.get(kind)
            if isinstance(bucket, dict) and name in bucket:
                return Resolved(bucket.get(name), 'runtime')

    pv = {}
    try:
        if isinstance(project, dict):
            pv = project.get('variables') or {}
        else:
            pv = getattr(project, 'variables', None) or {}
    except Exception:
        pv = {}
    if isinstance(pv, dict):
        bucket = pv.get(kind)
        if isinstance(bucket, dict) and name in bucket:
            return Resolved(bucket.get(name), 'project')
    return Resolved(default, 'default')

def resolve_project_ui_field(*, project: Any, field: str, default: Any = None) -> Resolved:
    field = str(field or '').strip()
    ui = _ui_dict(project)
    if field == 'selected_layer':
        try:
            fallback = default if default is not None else -1
            return Resolved(int(ui.get('selected_layer', fallback)), 'project' if 'selected_layer' in ui else 'default')
        except Exception:
            return Resolved(default if default is not None else -1, 'default')
    if field == 'era_id':
        if 'era_id' in ui:
            try:
                return Resolved(str(ui.get('era_id') or ''), 'project')
            except Exception:
                return Resolved(default, 'default')
        return Resolved(default, 'default')
    if field == 'target_mask':
        if 'target_mask' in ui:
            try:
                val = ui.get('target_mask')
                return Resolved(None if val in (None, '') else str(val), 'project')
            except Exception:
                return Resolved(default, 'default')
        return Resolved(default, 'default')
    return Resolved(default, 'default')

def resolve_project_audio_field(*, project: Any, field: str, default: Any = None) -> Resolved:
    field = str(field or '').strip()
    audio = _audio_dict(project)
    if field == 'routes':
        val = audio.get('routes', default if default is not None else [])
        return Resolved(val if isinstance(val, list) else (default if default is not None else []), 'project' if audio.get('routes', None) is not None else 'default')
    if field == 'preset_name':
        if audio.get('preset_name', None) is not None:
            return Resolved(str(audio.get('preset_name') or ''), 'project')
        return Resolved(default, 'default')
    return Resolved(default, 'default')

def resolve_signal_value(*, runtime: Optional[Dict[str, Any]] = None, key: str, default: Any = None) -> Resolved:
    skey = str(key or '').strip()
    if not skey:
        return Resolved(default, 'default')
    rt = runtime or {}
    sigs = rt.get('signals') if isinstance(rt, dict) else None
    if isinstance(sigs, dict) and skey in sigs:
        return Resolved(sigs.get(skey), 'runtime')
    return Resolved(default, 'default')

def resolver_registry() -> Dict[str, Dict[str, Any]]:
    return canonical_registry()

def resolve_address(*, project: Any, address: str, runtime: Optional[Dict[str, Any]] = None, default: Any = None) -> Resolved:
    parsed = parse_canonical_address(address)
    if parsed is None:
        return Resolved(default, 'default')
    if parsed.scope == 'layer_field' and parsed.layer_index is not None:
        return resolve_layer_field(project=project, layer_index=parsed.layer_index, field=parsed.key, runtime=runtime, default=default)
    if parsed.scope == 'project_postfx':
        pf, source = resolve_project_postfx(project=project, runtime=runtime)
        if parsed.key in pf:
            return Resolved(pf.get(parsed.key), source)
        return Resolved(default, 'default')
    if parsed.scope == 'project_layout':
        return resolve_project_surface_field(project=project, field=parsed.key, default=default)
    if parsed.scope == 'project_spatial':
        return resolve_project_spatial_field(project=project, field=parsed.key, default=default)
    if parsed.scope == 'project_variable':
        return resolve_project_variable(project=project, runtime=runtime, key=parsed.key, default=default)
    if parsed.scope == 'project_ui':
        return resolve_project_ui_field(project=project, field=parsed.key, default=default)
    if parsed.scope == 'project_audio':
        return resolve_project_audio_field(project=project, field=parsed.key, default=default)
    if parsed.scope == 'signal':
        return resolve_signal_value(runtime=runtime, key=parsed.key, default=default)
    if parsed.scope == 'system_state':
        return resolve_system_state(project=project, runtime=runtime, key=parsed.key, default=default)
    if parsed.scope == 'operator_param' and parsed.layer_index is not None:
        L = _layer_dict(project, parsed.layer_index)
        ov = dict(L.get('_op_overrides') or {}) if isinstance(L, dict) and isinstance(L.get('_op_overrides'), dict) else {}
        if parsed.key in ov:
            return Resolved(ov.get(parsed.key), 'project')
        return Resolved(default, 'default')
    return Resolved(default, 'default')




def resolve_project_layout_field(*, project: Any, field: str, default: Any = None) -> Resolved:
    """Compatibility wrapper for older callers.

    Canonical reads should use resolve_project_surface_field(...).
    """
    return resolve_project_surface_field(project=project, field=field, default=default)
