from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.surface_compat import canonicalize_surface_geometry, get_surface_kind_value, normalize_surface_kind
from runtime.canonical_addr import ParsedAddress, clamp01, normalize_blend_mode, parse_bool, parse_canonical_address
from runtime.resolver_types import _layout_dict

def _normalize_layout_after_write(layout: Dict[str, Any]) -> Dict[str, Any]:
    lay = canonicalize_surface_geometry(surface=dict(layout or {}))
    lay['kind'] = get_surface_kind_value(lay, default='strip')
    mapping = dict(lay.get('mapping') or {}) if isinstance(lay.get('mapping'), dict) else {}
    lay['mapping'] = mapping
    lay.pop('shape', None)
    for key in ('serpentine', 'flip_x', 'flip_y', 'rotate', 'origin'):
        lay.pop(key, None)
    return lay

def _coerce_for_parsed(parsed: ParsedAddress, value: Any) -> Tuple[bool, Any]:
    if parsed.scope == 'layer_field':
        if parsed.key == 'enabled':
            b = parse_bool(value)
            return (b is not None), bool(b) if b is not None else None
        if parsed.key == 'opacity':
            v = clamp01(value)
            return (v is not None), v
        if parsed.key == 'blend_mode':
            v = normalize_blend_mode(value)
            return (v is not None), v
        if parsed.key == 'order':
            try:
                return True, int(value)
            except Exception:
                return False, None
    if parsed.scope == 'project_layout':
        if parsed.key in ('kind', 'origin'):
            s = str(value or '').strip().lower()
            if parsed.key == 'kind':
                normalized = normalize_surface_kind(s, default='')
                if normalized in ('strip', 'cells'):
                    return True, normalized
                return False, None
            if s in ('top_left', 'top_right', 'bottom_left', 'bottom_right'):
                return True, s
            return False, None
        if parsed.key in ('serpentine', 'flip_x', 'flip_y'):
            b = parse_bool(value)
            return (b is not None), bool(b) if b is not None else None
        if parsed.key == 'rotate':
            try:
                v = int(value) % 360
            except Exception:
                return False, None
            if v not in (0, 90, 180, 270):
                return False, None
            return True, v
        try:
            v = int(value)
        except Exception:
            return False, None
        return (v > 0), v if v > 0 else None
    if parsed.scope == 'project_variable':
        kind = str(parsed.key or '').split('.', 1)[0]
        if kind == 'toggle':
            b = parse_bool(value)
            return (b is not None), bool(b) if b is not None else None
        try:
            return True, float(value)
        except Exception:
            return False, None
    if parsed.scope == 'project_spatial':
        if parsed.key in ('enabled','mirror_x','mirror_y','use_layout_coords'):
            b = parse_bool(value)
            return (b is not None), bool(b) if b is not None else None
        try:
            return True, float(value)
        except Exception:
            return False, None
    if parsed.scope == 'project_ui':
        if parsed.key == 'selected_layer':
            try:
                return True, int(value)
            except Exception:
                return False, None
        if parsed.key == 'era_id':
            try:
                return True, str(value or '')
            except Exception:
                return False, None
        if parsed.key == 'target_mask':
            if value in (None, ''):
                return True, None
            try:
                return True, str(value)
            except Exception:
                return False, None
        return False, None
    if parsed.scope == 'project_audio':
        if parsed.key == 'routes':
            return (isinstance(value, list)), list(value) if isinstance(value, list) else None
        if parsed.key == 'preset_name':
            try:
                return True, str(value or '')
            except Exception:
                return False, None
        return False, None
    if parsed.scope in ('project_postfx', 'operator_param'):
        try:
            return True, float(value)
        except Exception:
            return False, None
    return True, value

def set_address(*, project: Any, address: str, value: Any, allow_alias: bool = False) -> Tuple[Any, bool]:
    parsed = parse_canonical_address(address)
    if parsed is None:
        return project, False

    # Writes must be canonical-only. Aliases are tolerated for reads during migration,
    # but any write via an alias is considered a legacy split path.
    if getattr(parsed, 'was_alias', False) and not allow_alias:
        return project, False

    ok, coerced = _coerce_for_parsed(parsed, value)
    if not ok:
        return project, False

    p = dict(project or {}) if isinstance(project, dict) else {}
    if parsed.scope == 'project_layout':
        surface = dict(p.get('surface') or {}) if isinstance(p.get('surface'), dict) else {}
        mapping_keys = {'serpentine', 'flip_x', 'flip_y', 'rotate', 'origin'}
        if parsed.key in mapping_keys:
            mapping = dict(surface.get('mapping') or {}) if isinstance(surface.get('mapping'), dict) else {}
            if mapping.get(parsed.key) == coerced and 'layout' not in p:
                return p, False
            mapping[parsed.key] = coerced
            surface['mapping'] = mapping
        else:
            if surface.get(parsed.key) == coerced and 'layout' not in p:
                return p, False
            surface[parsed.key] = coerced
            if parsed.key == 'kind':
                surface['kind'] = coerced
        surface = _normalize_layout_after_write(surface)
        if p.get('surface') == surface and 'layout' not in p:
            return p, False
        p['surface'] = surface
        p.pop('layout', None)
        return p, True
    if parsed.scope == 'project_postfx':
        postfx = dict(p.get('postfx') or {}) if isinstance(p.get('postfx'), dict) else {}
        if postfx.get(parsed.key) == coerced:
            return p, False
        postfx[parsed.key] = coerced
        p['postfx'] = postfx
        return p, True
    if parsed.scope == 'project_spatial':
        spatial = dict(p.get('spatial') or {}) if isinstance(p.get('spatial'), dict) else {}
        if parsed.key in ('origin_x','origin_y'):
            origin = list(spatial.get('origin') or [0.0, 0.0])
            while len(origin) < 2:
                origin.append(0.0)
            idx = 0 if parsed.key.endswith('_x') else 1
            if origin[idx] == coerced:
                return p, False
            origin[idx] = coerced
            spatial['origin'] = [float(origin[0]), float(origin[1])]
        else:
            if spatial.get(parsed.key) == coerced:
                return p, False
            spatial[parsed.key] = coerced
        p['spatial'] = spatial
        return p, True
    if parsed.scope == 'project_variable':
        vars_dict = dict(p.get('variables') or {}) if isinstance(p.get('variables'), dict) else {}
        kind, name = str(parsed.key or '').split('.', 1)
        bucket = dict(vars_dict.get(kind) or {}) if isinstance(vars_dict.get(kind), dict) else {}
        if bucket.get(name) == coerced:
            return p, False
        bucket[name] = coerced
        vars_dict[kind] = bucket
        p['variables'] = vars_dict
        return p, True
    if parsed.scope == 'project_ui':
        ui = dict(p.get('ui') or {}) if isinstance(p.get('ui'), dict) else {}
        if parsed.key == 'target_mask' and coerced is None:
            if 'target_mask' not in ui:
                return p, False
            ui.pop('target_mask', None)
            p['ui'] = ui
            return p, True
        if ui.get(parsed.key) == coerced:
            return p, False
        ui[parsed.key] = coerced
        p['ui'] = ui
        return p, True
    if parsed.scope == 'project_audio':
        audio = dict(p.get('audio') or {}) if isinstance(p.get('audio'), dict) else {}
        if audio.get(parsed.key) == coerced and 'audio_routes' not in p and 'audio_preset_name' not in p:
            return p, False
        audio[parsed.key] = coerced
        p['audio'] = audio
        p.pop('audio_routes', None)
        p.pop('audio_preset_name', None)
        return p, True

    layers = list(p.get('layers') or []) if isinstance(p.get('layers'), list) else []
    li = int(parsed.layer_index or 0)
    if li < 0 or li >= len(layers) or not isinstance(layers[li], dict):
        return p, False
    L = dict(layers[li] or {})

    if parsed.scope == 'layer_field':
        oldv = L.get(parsed.key)
        changed = (oldv != coerced)
        L[parsed.key] = coerced
        if parsed.key == 'blend_mode':
            L.pop('blend', None)
        # Canonical composition fields live only on the layer root.
        # Do NOT mirror layer.opacity into params.opacity here.
        if not changed:
            return p, False
        layers[li] = L
        p['layers'] = layers
        return p, True

    if parsed.scope == 'operator_param':
        ov = dict(L.get('_op_overrides') or {}) if isinstance(L.get('_op_overrides'), dict) else {}
        if ov.get(parsed.key) == coerced:
            return p, False
        ov[parsed.key] = coerced
        L['_op_overrides'] = ov
        layers[li] = L
        p['layers'] = layers
        return p, True

    return p, False
