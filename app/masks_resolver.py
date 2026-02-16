from __future__ import annotations

"""Mask Resolver

Resolve a mask reference (by key or inline spec) into an index set.

Supported mask node shapes:
- indices mask:
    {"indices": [0,1,2]}
- zone/range mask (inclusive):
    {"start": 10, "end": 20}
- composed op mask:
    {"op": "union"|"intersect"|"subtract"|"xor", "a": <maskRef>, "b": <maskRef>}

maskRef may be:
- a string key referring to project["masks"][key]
- an inline mask dict of any supported shape
- a list/tuple/set of indices
"""

from typing import Any, Dict, Optional, Set

from app.zones_ops_registry import get_zone_op, normalize_to_index_set


def resolve_mask_to_indices(project: Dict[str, Any], mask_ref: Any, *, n: Optional[int] = None, _depth: int = 0, _seen: Optional[Set[str]] = None) -> Set[int]:
    if _depth > 16:
        return set()
    if _seen is None:
        _seen = set()

    if mask_ref is None:
        return set()

    # Key ref into project["masks"]
    if isinstance(mask_ref, str):
        k = mask_ref.strip()
        if not k:
            return set()
        if k in _seen:
            return set()
        _seen.add(k)
        masks = (project or {}).get("masks") or {}
        node = masks.get(k)
        return resolve_mask_to_indices(project, node, n=n, _depth=_depth+1, _seen=_seen)

    # Inline dict
    if isinstance(mask_ref, dict):
        # composition
        if "op" in mask_ref and ("a" in mask_ref or "b" in mask_ref):
            op_key = str(mask_ref.get("op") or "").strip().lower()
            op = get_zone_op(op_key)
            if not op:
                return set()
            a = resolve_mask_to_indices(project, mask_ref.get("a"), n=n, _depth=_depth+1, _seen=_seen)
            b = resolve_mask_to_indices(project, mask_ref.get("b"), n=n, _depth=_depth+1, _seen=_seen)
            try:
                out = op.fn(set(a), set(b))
            except Exception:
                out = set()
            return normalize_to_index_set(list(out), n=n)

        # base shapes
        return normalize_to_index_set(mask_ref, n=n)

    # list/set/tuple
    return normalize_to_index_set(mask_ref, n=n)
def resolve_target_mask_for_layer(layer_dict, project_dict, n=None):
    """Compatibility wrapper used by PreviewEngine and legacy callers.

    Returns (mask_key, indices_set).
    - mask_key is the resolved key from project['ui']['target_mask'] if present.
    - indices_set is a set[int] of resolved indices.
    """
    project = project_dict or {}
    ui = project.get("ui") or {}
    mask_key = ui.get('target_mask') or (layer_dict or {}).get('target_mask')
    if mask_key is None or mask_key == "" or mask_key == 0:
        return (None, set())
    idxs = resolve_mask_to_indices(project, mask_key, n=n)
    return (mask_key, idxs)
