from __future__ import annotations

import inspect

from core.surface_compat import get_surface_geometry_values

from behaviors.state import EffectContext
from app.project_model import get_surface_snapshot, get_surface_kind, get_surface_dimensions, get_default_surface_dict

# Runtime-only cache to persist *project-level* PostFX temporal state across PreviewEngine rebuilds.
_PROJECT_POSTFX_CACHE = {}


def _postfx_project_key(project):
    # 1) Prefer (and if missing, stamp) an explicit runtime cache key on project.postfx.
    try:
        pfx = getattr(project, 'postfx', None)
        if isinstance(pfx, dict):
            k = pfx.get('_rt_cache_key')
            if not k:
                k = f"auto_{id(project)}"
                pfx['_rt_cache_key'] = k
            return ('rt', str(k))
    except Exception as e:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain="PREVIEW", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"preview/preview_engine.py"})
        pass

    # 2) Content-derived key.
    try:
        layers = getattr(project, 'layers', None) or []
        ident = []
        for i, l in enumerate(layers):
            if isinstance(l, dict):
                ident.append(l.get('name') or l.get('uid') or f'#{i}')
            else:
                ident.append(f'#{i}')
        ident = tuple(sorted([str(x) for x in ident]))
        surface = get_surface_snapshot(project)
        if not isinstance(surface, dict):
            surface = get_default_surface_dict()
        # Canonical runtime path: preview identity must derive from the canonical surface snapshot only.
        if callable(get_surface_kind) and callable(get_surface_dimensions):
            kind = get_surface_kind(project)
            w, h = get_surface_dimensions(project)
        else:
            kind, _count, w, h = get_surface_geometry_values(surface, default_kind='strip', default_count=0)
        return ('sig', str(kind), int(w or 0), int(h or 0), ident)
    except Exception as e:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain="PREVIEW", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"preview/preview_engine.py"})
        pass

    return ('id', id(project))


def _call_preview_emit(beh, *, num_leds: int, params: dict, t: float, state: dict, surface: dict, dt: float, audio: dict):
    fn = getattr(beh, "preview_emit", None)
    if fn is None:
        return [(0, 0, 0)] * int(num_leds)

    surface = dict(surface) if isinstance(surface, dict) else get_default_surface_dict()
    ctx = EffectContext(surface=surface, dt=float(dt), t=float(t), audio=dict(audio or {}))
    out_buf = [(0, 0, 0)] * int(num_leds)

    if isinstance(params, dict):
        _p = params
        try:
            a = audio if isinstance(audio, dict) else {}
            mono = list(a.get('mono') or [0.0] * 7)
            l = list(a.get('L') or a.get('l') or [0.0] * 7)
            r = list(a.get('R') or a.get('r') or [0.0] * 7)
            if len(mono) < 7:
                mono = (mono + [0.0] * 7)[:7]
            if len(l) < 7:
                l = (l + [0.0] * 7)[:7]
            if len(r) < 7:
                r = (r + [0.0] * 7)[:7]
            energy = float(a.get('energy', 0.0) or 0.0)
            af = {'energy': energy}
            for i in range(7):
                af[f'mono{i}'] = float(mono[i])
                af[f'l{i}'] = float(l[i])
                af[f'r{i}'] = float(r[i])
            if _p is params:
                _p = dict(_p)
            _p['_audio_flat'] = af
            _p.setdefault('_audio_tempo', {'bpm': 120.0})
            prev = _p.get('_audio_prev')
            if not isinstance(prev, dict):
                prev = {}
            ev = {'energy': energy}
            ev['energy_l'] = sum(af[f'l{i}'] for i in range(7)) / 7.0
            ev['energy_r'] = sum(af[f'r{i}'] for i in range(7)) / 7.0
            for i in range(7):
                lv = af[f'l{i}']; rv = af[f'r{i}']; mv = af[f'mono{i}']
                ev[f'l{i}_level'] = lv
                ev[f'r{i}_level'] = rv
                ev[f'mono{i}_level'] = mv
                pl = float(prev.get(f'l{i}', lv))
                pr = float(prev.get(f'r{i}', rv))
                pm = float(prev.get(f'mono{i}', mv))
                ev[f'l{i}_tr'] = max(0.0, lv - pl)
                ev[f'r{i}_tr'] = max(0.0, rv - pr)
                ev[f'mono{i}_tr'] = max(0.0, mv - pm)
                prev[f'l{i}'] = lv
                prev[f'r{i}'] = rv
                prev[f'mono{i}'] = mv
            _p['_audio_prev'] = prev
            _p['_audio_events'] = ev
            for i in range(7):
                _p.setdefault(f'purpose_f{i}', af[f'mono{i}'])
            _p.setdefault('purpose_energy', energy)
        except Exception:
            pass
        params = _p

    try:
        sig = inspect.signature(fn)
        want = sig.parameters
    except Exception:
        want = {}

    candidates = {
        'num_leds': int(num_leds),
        'n': int(num_leds),
        'count': int(num_leds),
        'params': params,
        't': float(t),
        'time': float(t),
        'dt': float(dt),
        'state': state,
        'ctx': ctx,
        'context': ctx,
        'surface': surface,
        'audio': dict(audio or {}),
        'out': out_buf,
        'buf': out_buf,
        'pixels': out_buf,
        'leds': out_buf,
    }

    if want:
        kw = {k: v for k, v in candidates.items() if k in want}
        has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in want.values())
        if has_varkw:
            # Canonical preview runtime should always provide ``surface``.
            # Do not auto-inject a second live geometry slot under the old
            # Preview behaviors consume canonical surface data only.
            # ``surface`` truth.
            for k in ('num_leds', 'params', 't', 'dt', 'state', 'ctx', 'surface', 'audio', 'out', 'buf', 'pixels', 'leds'):
                kw.setdefault(k, candidates[k])
    else:
        kw = {'num_leds': int(num_leds), 'params': params, 't': float(t)}

    res = fn(**kw)
    if res is None:
        return out_buf
    return list(res)


def get_layer_state(self, layer_id: str) -> dict:
    try:
        for L in (self.layers or []):
            if str(getattr(L, 'id', None)) == str(layer_id):
                st = getattr(L, '_state', None)
                return dict(st) if isinstance(st, dict) else {}
    except Exception as e:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain="PREVIEW", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"preview/preview_engine.py"})
        pass
    return {}


def get_runtime_stats(self, layer_id: str) -> dict:
    try:
        st = self._state_map.get(str(layer_id))
        if st is None:
            return {}
        data = getattr(st, "data", None)
        out = {}
        if isinstance(data, dict):
            for k in ("score", "health", "ammo", "cool", "cooldown", "lives"):
                if k in data:
                    out[k] = data.get(k)
            if "blocks" in data and isinstance(data.get("blocks"), list):
                out["blocks_left"] = sum(1 for v in data["blocks"] if int(v) > 0)
        try:
            _sig = []
            _en = 0
            for i, layer in enumerate(self.layers):
                enabled = bool(self._layer_field(i, 'enabled', True))
                if enabled:
                    _en += 1
                _sig.append({
                    'i': i,
                    'id': _pe_get(layer, 'id', _pe_get(layer, 'uid', None)),
                    'behavior': str(_pe_get(layer, 'behavior', None) or 'solid'),
                    'enabled': enabled,
                })
            out['_layers_signature'] = {'enabled_n': _en, 'layers': _sig}
        except Exception:
            pass
        return out
    except Exception as e:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain="PREVIEW", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"preview/preview_engine.py"})
        return {}


def get_live_params(self):
    try:
        return list(getattr(self, '_last_live_rows', []) or [])
    except Exception:
        return []


def get_layer_stats(self):
    try:
        return dict(getattr(self, '_last_layer_stats', {}) or {})
    except Exception:
        return {}


def _pe_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _pe_set(obj, key, value):
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)
