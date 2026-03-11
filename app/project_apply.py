from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Tuple

from app.project_defaults import DEFAULT_PROJECT


def copy_project(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return an isolated project copy for canonicalization/update work.

    Canonicalization mutates nested structures in-place while it removes legacy keys,
    stamps defaults, and assigns stable runtime ids. A shallow top-level copy lets
    those mutations leak back into the caller's project dict, which creates split
    behavior between probes/UI/runtime and makes list-order checks lie.
    """
    if not isinstance(project, dict):
        return copy.deepcopy(DEFAULT_PROJECT)
    try:
        return copy.deepcopy(project)
    except Exception:
        # Fallback for any unexpected non-deepcopyable payloads; keep isolation.
        return json.loads(json.dumps(project, default=str))


def replace_project_roots(project: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Pure top-level replacement helper.

    This intentionally does *not* re-enter canonicalization. It is used by the
    canonical normalization pipeline itself to avoid recursive finalize calls
    and import cycles.
    """
    p = copy_project(project)
    for key, value in dict(updates or {}).items():
        p[str(key)] = value
    return p


def replace_project_root(project: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    return replace_project_roots(project, {str(key): value})


def apply_project_roots(
    project: Dict[str, Any],
    updates: Dict[str, Any],
    *,
    sanitize_for_era: bool = False,
    enforce_era: bool = False,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Canonical top-level update entrypoint for runtime/UI mutations."""
    from app.project_canonical import finalize_project_dict

    p = replace_project_roots(project, updates)
    return finalize_project_dict(
        p,
        sanitize_for_era=sanitize_for_era,
        enforce_era=enforce_era,
        validate=validate,
    )


def apply_project_root(
    project: Dict[str, Any],
    key: str,
    value: Any,
    *,
    sanitize_for_era: bool = False,
    enforce_era: bool = False,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    return apply_project_roots(
        project,
        {str(key): value},
        sanitize_for_era=sanitize_for_era,
        enforce_era=enforce_era,
        validate=validate,
    )
