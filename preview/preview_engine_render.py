from __future__ import annotations

import traceback
from typing import List, Tuple

from behaviors.registry import REGISTRY
from behaviors.state import EffectState
from preview import postfx
from preview.preview_engine_support import (
    _PROJECT_POSTFX_CACHE,
    _call_preview_emit,
    _pe_get,
    _postfx_project_key,
)
from runtime.resolver import resolve_layer_field, resolve_project_postfx

RGB = Tuple[int, int, int]


class PreviewEngineRenderMixin:
    @property
    def layers(self):
        return list(_pe_get(self.project, 'layers', []) or [])

    def _surface(self):
        try:
            from app.project_model import get_surface_runtime_snapshot
            return dict(get_surface_runtime_snapshot(self.project) or {})
        except Exception:
            try:
                from app.project_model import build_surface_from_evidence, get_default_surface_dict
            except Exception:
                build_surface_from_evidence = None
                get_default_surface_dict = None
            if callable(build_surface_from_evidence):
                raw_surface = _pe_get(self.project, 'surface', {}) or {}
                if isinstance(raw_surface, dict) and raw_surface:
                    try:
                        return build_surface_from_evidence(raw_surface, default_kind='strip', default_count=144)
                    except Exception:
                        pass
            if callable(get_default_surface_dict):
                return get_default_surface_dict(kind='strip', count=144)
            from core.surface_compat import get_default_surface_dict as _core_get_default_surface_dict
            return _core_get_default_surface_dict(kind='strip', count=144)

    def _audio_dict(self, t: float):
        audio = self.audio
        try:
            if hasattr(audio, 'step'):
                audio.step(float(t))
        except Exception:
            pass
        if hasattr(audio, 'state') and isinstance(audio.state, dict):
            return dict(audio.state)
        return {'energy': 0.0, 'mono': [0.0] * 7, 'L': [0.0] * 7, 'R': [0.0] * 7}

    def _layer_field(self, i: int, field: str, default):
        try:
            return resolve_layer_field(project=self.project, layer_index=int(i), field=str(field), runtime=None).value
        except Exception:
            layer = self.layers[i] if 0 <= i < len(self.layers) else {}
            try:
                return _pe_get(layer, field, default)
            except Exception:
                return default

    def render_project(self, project, *, t: float | None = None, dt: float | None = None, audio=None):
        old_project = self.project
        old_audio = self.audio
        old_dt = self.fixed_dt
        try:
            self.project = project or {}
            self.project_data = self.project
            if audio is not None:
                self.audio = audio
            if dt is not None:
                self.fixed_dt = float(dt)
            leds = self.render_frame(t)
            return {'leds': list(leds or []), 'last_error': self.last_error, 'stats': dict(self._last_render_stats or {})}
        finally:
            self.project = old_project
            self.project_data = self.project
            self.audio = old_audio
            self.fixed_dt = old_dt

    def render_frame(self, t: float | None = None):
        import time as _time
        if t is None:
            t = _time.time()
        try:
            surface = self._surface()
            try:
                from app.project_model import get_surface_geometry_values
                surface_kind, n, _surface_width, _surface_height = get_surface_geometry_values(surface, default_kind='strip', default_count=144)
            except Exception:
                try:
                    from core.surface_compat import get_surface_geometry_values as _core_get_surface_geometry_values
                    surface_kind, n, _surface_width, _surface_height = _core_get_surface_geometry_values(surface, default_kind='strip', default_count=144)
                except Exception:
                    from core.surface_compat import get_surface_kind_value as _get_surface_kind_value
                    surface_kind = _get_surface_kind_value(surface, default='strip')
                    n = int(surface.get('count') or (int(surface.get('width') or 1) * int(surface.get('height') or 1)) or 1)
            out = [(0, 0, 0)] * max(1, n)
            audio_dict = self._audio_dict(float(t))
            enabled_n = 0
            sig = []
            ordered_layers = []
            for i, layer in enumerate(self.layers):
                enabled = bool(self._layer_field(i, 'enabled', True))
                _opacity_raw = self._layer_field(i, 'opacity', 1.0)
                try:
                    opacity = float(1.0 if _opacity_raw is None else _opacity_raw)
                except Exception:
                    opacity = 1.0
                blend = str(self._layer_field(i, 'blend_mode', 'over') or 'over').strip().lower()
                try:
                    order = int(self._layer_field(i, 'order', i))
                except Exception:
                    order = i
                effect_id = str(_pe_get(layer, 'behavior', None) or 'solid').strip()
                params = dict(_pe_get(layer, 'params', {}) or {})
                sig.append({'i': i, 'id': _pe_get(layer, 'id', _pe_get(layer, 'uid', None)), 'name': _pe_get(layer, 'name', None), 'behavior': effect_id, 'enabled': enabled, 'opacity': opacity, 'blend_mode': blend, 'order': order})
                ordered_layers.append((order, i, layer, enabled, opacity, blend, effect_id, params))
            ordered_layers.sort(key=lambda x: (x[0], x[1]))
            for order, i, layer, enabled, opacity, blend, effect_id, params in ordered_layers:
                if not enabled:
                    continue
                enabled_n += 1
                beh = REGISTRY.get(effect_id) or REGISTRY.get('solid')
                if beh is None:
                    continue
                state = self._state_by_uid.setdefault(str(_pe_get(layer, 'id', _pe_get(layer, 'uid', i))), EffectState())
                frame = _call_preview_emit(beh, num_leds=n, params=params, t=float(t), state=state, surface=surface, dt=self.fixed_dt, audio=audio_dict)
                if not isinstance(frame, list):
                    frame = [(0, 0, 0)] * n
                if len(frame) < n:
                    frame = list(frame) + [(0, 0, 0)] * (n - len(frame))
                elif len(frame) > n:
                    frame = list(frame)[:n]
                frame = self._apply_layer_operators(layer, effect_id, frame)
                out = self._blend(out, frame, blend, opacity)
                self._last_layer_stats[str(_pe_get(layer, 'id', _pe_get(layer, 'uid', i)))] = {
                    'enabled': enabled,
                    'opacity': opacity,
                    'blend_mode': blend,
                    'behavior': effect_id,
                    'order': order,
                    'nonzero': sum(1 for px in frame if px[0] or px[1] or px[2]),
                }
            self._last_layers_signature = {'enabled_n': enabled_n, 'layers': sig}

            pf, _pf_source = resolve_project_postfx(project=self.project, runtime=None)
            cache_key = _postfx_project_key(self.project)
            prev_postfx = _PROJECT_POSTFX_CACHE.get(cache_key)
            out, new_prev = postfx.apply_postfx(
                list(out),
                surface=surface,
                postfx=pf,
                prev=prev_postfx,
                neighbors=None,
            )
            if new_prev is None:
                _PROJECT_POSTFX_CACHE.pop(cache_key, None)
            else:
                _PROJECT_POSTFX_CACHE[cache_key] = list(new_prev)

            self._last_render_stats = {'ts': _time.time(), 'count': n, 'surface_kind': surface_kind or 'strip', 'layers_n': len(self.layers), 'nonzero': sum(1 for px in out if px[0] or px[1] or px[2]), 'last_error': '', 'postfx_source': _pf_source}
            self._last_frame = list(out)
            self.last_error = None
            self.last_traceback = None
            return list(out)
        except Exception as e:
            self.last_error = f'{type(e).__name__}: {e}'
            self.last_traceback = traceback.format_exc()
            try:
                from app.project_model import get_surface_geometry_values
                _fallback_kind, n, _fallback_width, _fallback_height = get_surface_geometry_values(self._surface() or {}, default_kind='strip', default_count=144)
            except Exception:
                try:
                    n = int((self._surface() or {}).get('count') or 144)
                except Exception:
                    n = 144
            self._last_frame = [(0, 0, 0)] * max(1, n)
            return list(self._last_frame)

    def get_pixels(self) -> List[RGB]:
        return list(self._last_frame or [])

    def get_layer_state(self, layer_id: str) -> dict:
        st = self._state_by_uid.get(str(layer_id))
        data = getattr(st, 'data', None) if st is not None else None
        return dict(data) if isinstance(data, dict) else {}

    def get_runtime_stats(self, layer_id: str) -> dict:
        return dict(self._last_layer_stats.get(str(layer_id)) or {})

    def get_live_params(self):
        return list(self._last_live_rows or [])

    def get_layer_stats(self):
        return dict(self._last_layer_stats or {})
