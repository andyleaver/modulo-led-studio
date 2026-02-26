
from __future__ import annotations

"""Masks API (Phase A1 safe foundation)

Provides non-UI helper functions to create and validate masks in a project dict.

This is intentionally small and pure:
- It does not know about Qt/Tk
- It does not mutate global state
- It returns new project dicts (copy-on-write style) unless explicitly asked to mutate.

Mask node shapes supported match app.masks_resolver.
"""

from typing import Any, Dict, Optional, Tuple
import copy

from app.masks_resolver import resolve_mask_to_indices

_ALLOWED_OPS = {"union", "intersect", "subtract", "xor"}


def ensure_masks_dict(project: Dict[str, Any]) -> Dict[str, Any]:
    p = project if isinstance(project, dict) else {}
    if not isinstance(p.get("masks"), dict):
        p = dict(p)
        p["masks"] = {}
    return p


def create_composed_mask(
    project: Dict[str, Any],
    key: str,
    op: str,
    a: Any,
    b: Any,
    *,
    validate: bool = True,
    n: Optional[int] = None,
) -> Dict[str, Any]:
    """Return a new project with a composed mask inserted.

    key: mask id string in project["masks"]
    op: one of union/intersect/subtract/xor
    a,b: mask refs (string key / inline dict / indices list)
    validate: if True, attempt to resolve the new mask; raise on failure.
    n: optional clamp count.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("key must be a non-empty string")
    op = str(op or "").strip()
    if op not in _ALLOWED_OPS:
        raise ValueError(f"Unsupported op: {op}")

    p = ensure_masks_dict(project)
    masks = dict(p.get("masks") or {})
    if key in masks:
        raise ValueError(f"mask key already exists: {key}")

    masks[key] = {"op": op, "a": a, "b": b}
    p2 = dict(p)
    p2["masks"] = masks

    if validate:
        # Raises on cycle/unknown op/etc.
        resolve_mask_to_indices(p2, key, n=n)

    return p2


def validate_all_masks(project: Dict[str, Any], *, n: Optional[int] = None) -> Tuple[bool, Dict[str, str]]:
    """Validate all masks resolve. Returns (ok, errors_by_key)."""
    errors: Dict[str, str] = {}
    masks = (project or {}).get("masks") or {}
    if not isinstance(masks, dict):
        return True, {}
    for k in sorted(masks.keys()):
        try:
            resolve_mask_to_indices(project, str(k), n=n)
        except Exception as e:
            errors[str(k)] = str(e)
    return (len(errors) == 0), errors
