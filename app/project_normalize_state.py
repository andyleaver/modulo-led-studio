from typing import Any, Dict, List

from app.project_apply import replace_project_root
from .project_normalize_support import diag_exc


def normalize_state(project: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    p = dict(project)

    audio = p.get('audio')
    if not isinstance(audio, dict):
        audio = {}
    if 'routes' not in audio and 'audio_routes' in p:
        routes = p.get('audio_routes')
        if isinstance(routes, list):
            audio['routes'] = list(routes)
            changes.append('migrated top-level audio_routes -> audio.routes')
    if 'preset_name' not in audio and 'audio_preset_name' in p:
        try:
            audio['preset_name'] = str(p.get('audio_preset_name') or '')
            changes.append('migrated top-level audio_preset_name -> audio.preset_name')
        except Exception:
            pass
    if 'audio_routes' in p:
        del p['audio_routes']
        changes.append('removed deprecated top-level audio_routes')
    if 'audio_preset_name' in p:
        del p['audio_preset_name']
        changes.append('removed deprecated top-level audio_preset_name')
    routes = audio.get('routes', None)
    if not isinstance(routes, list):
        audio['routes'] = []
        changes.append('canonicalized audio.routes to list')
    preset_name = audio.get('preset_name', '')
    if not isinstance(preset_name, str):
        audio['preset_name'] = str(preset_name or '')
        changes.append('canonicalized audio.preset_name to str')
    if audio or 'audio' in p:
        p = replace_project_root(p, 'audio', audio)

    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
        p = replace_project_root(p, 'ui', ui)
    if 'selected_layer' not in ui and 'active_layer' in p:
        try:
            ui['selected_layer'] = int(p.get('active_layer', 0) or 0)
            changes.append('migrated top-level active_layer -> ui.selected_layer')
        except Exception:
            ui['selected_layer'] = 0
    layers = p.get('layers') or []
    try:
        selected = int(ui.get('selected_layer', 0) or 0)
    except Exception:
        selected = 0
    if isinstance(layers, list) and layers:
        selected = max(0, min(selected, len(layers) - 1))
    else:
        selected = -1
    ui['selected_layer'] = int(selected)
    if 'active_layer' in p:
        del p['active_layer']

    try:
        layers = p.get('layers') or []
        if isinstance(layers, list):
            layers2 = []
            for layer in layers:
                if not isinstance(layer, dict):
                    layers2.append(layer)
                    continue
                behavior = str(layer.get('behavior') or 'solid')
                operators = layer.get('operators')
                if not isinstance(operators, list):
                    operators = []
                clean = []
                for operator in operators:
                    if not isinstance(operator, dict):
                        continue
                    operator_type = str(operator.get('type') or '').strip()
                    if not operator_type:
                        continue
                    params = operator.get('params')
                    if not isinstance(params, dict):
                        params = {}
                    try:
                        operator_clean = {'type': operator_type, 'params': params, 'enabled': bool(operator.get('enabled', True))}
                    except Exception:
                        operator_clean = {'type': operator_type, 'params': params, 'enabled': True}
                    try:
                        target_kind = operator.get('target_kind')
                        if target_kind is not None and str(target_kind).strip():
                            operator_clean['target_kind'] = str(target_kind)
                    except Exception as error:
                        diag_exc(error, 'app/project_normalize_state.py')
                    try:
                        target_key = operator.get('target_key')
                        if target_key is not None and str(target_key).strip():
                            operator_clean['target_key'] = str(target_key)
                    except Exception as error:
                        diag_exc(error, 'app/project_normalize_state.py')
                    clean.append(operator_clean)
                if not clean:
                    clean = [{'type': behavior, 'params': {}, 'enabled': True}]
                elif str(clean[0].get('type') or '') != behavior:
                    clean[0] = {'type': behavior, 'params': dict(clean[0].get('params') or {}), 'enabled': True}
                layer2 = dict(layer)
                layer2['behavior'] = behavior
                layer2.pop('effect', None)
                layer2['operators'] = clean
                layers2.append(layer2)
            p = replace_project_root(p, 'layers', layers2)
    except Exception as error:
        diag_exc(error, 'app/project_normalize_state.py')

    return p
