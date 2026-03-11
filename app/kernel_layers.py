"""Kernel layer normalization and defaults.

Kernel is a first-class door. If a layer is marked kind='kernel' (or behavior
kernel / write_the_loop), we ensure it is structurally complete.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.project_canonical import apply_project_root

def ensure_kernel_layers(project: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(project, dict):
        return {}, True
    layers = project.get('layers')
    if not isinstance(layers, list):
        return project, False

    changed = False
    out_layers = []
    for L0 in layers:
        if not isinstance(L0, dict):
            out_layers.append(L0)
            continue
        L = dict(L0)
        beh = str(L.get('behavior') or '').strip()
        kind = str(L.get('kind') or '').strip().lower()

        is_kernel = (kind == 'kernel') or (beh in ('kernel','write_the_loop'))
        if is_kernel:
            # Canonicalize
            if L.get('kind') != 'kernel':
                L['kind'] = 'kernel'
                changed = True
            if L.get('behavior') not in ('kernel','write_the_loop'):
                L['behavior'] = 'kernel'
            elif L.get('behavior') == 'write_the_loop':
                # migrate legacy alias to canonical 'kernel'
                L['behavior'] = 'kernel'
                changed = True

            params = L.get('params') if isinstance(L.get('params'), dict) else {}
            params2 = dict(params)
            # Defaults
            if 'budget_ms' not in params2:
                params2['budget_ms'] = 10.0
                changed = True
            if 'strike_limit' not in params2:
                params2['strike_limit'] = 3
                changed = True
            if 'py' not in params2:
                params2['py'] = ''
                changed = True
            if 'cpp' not in params2:
                params2['cpp'] = ''
                changed = True
            # Optional: determinism defaults
            if 'deterministic' not in params2:
                params2['deterministic'] = True
                changed = True
            if 'seed' not in params2:
                params2['seed'] = 1337
                changed = True

            if params2 != params:
                L['params'] = params2
                changed = True

        out_layers.append(L if (L != L0) else L0)

    if changed:
        p2, _validation, _changes = apply_project_root(dict(project), 'layers', out_layers)
        return p2, True
    return project, False
