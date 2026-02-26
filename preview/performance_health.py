from __future__ import annotations

from typing import Any, Dict

from runtime.extensions_v1 import register_health_probe


def _probe() -> Dict[str, Any]:
    try:
        from preview.engine_registry import LAST_PREVIEW_ENGINE
        eng = LAST_PREVIEW_ENGINE
        if eng is None:
            return {'present': False}
        snap = getattr(eng, '_resource_snapshot', None)
        last = getattr(eng, '_last_render_stats', None)
        fps = getattr(eng, 'fps', None)
        out: Dict[str, Any] = {'present': True}
        if isinstance(fps, (int, float)):
            out['fps'] = float(fps)
        if isinstance(snap, dict):
            # keep this small + stable
            out['n_leds'] = snap.get('n_leds')
            out['enabled_layers'] = snap.get('enabled_layers')
            out['ops_est'] = snap.get('ops_est')
            out['tick_ms_avg'] = snap.get('tick_ms_avg')
            out['render_ms_avg'] = snap.get('render_ms_avg')
            out['frame_ms_avg'] = snap.get('frame_ms_avg')
            out['warnings'] = snap.get('warnings')
            out['last_layer_costs'] = snap.get('last_layer_costs')
        if isinstance(last, dict):
            out['last_nonzero'] = last.get('nonzero')
            out['layout_shape'] = last.get('layout_shape')
        return out
    except Exception as e:
        return {'present': False, 'error': f'{type(e).__name__}: {e}'}


register_health_probe('performance', _probe)
