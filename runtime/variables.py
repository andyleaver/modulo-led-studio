"""Variables helpers.

Persistent user variables that Rules/Triggers can read/write.

Stored in project schema::

    project["variables"] = {
      "number": {"<name>": float, ...},
      "toggle": {"<name>": bool, ...},
    }

Constraints:
- Names are explicit and stable (no implicit creation by Rules).
- Helpers are best-effort and never raise for malformed project data.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def ensure_variables(project: dict) -> Tuple[dict, bool]:
    """Ensure project has a well-formed canonical ``variables`` root.

    Returns ``(project2, changed)``.
    """
    p = dict(project) if isinstance(project, dict) else {}
    changed = False

    vars0 = p.get("variables")
    vars_dict: Dict[str, Any] = vars0 if isinstance(vars0, dict) else {}
    if not isinstance(vars0, dict):
        changed = True

    num0 = vars_dict.get("number")
    tog0 = vars_dict.get("toggle")
    num = num0 if isinstance(num0, dict) else {}
    tog = tog0 if isinstance(tog0, dict) else {}
    if not isinstance(num0, dict):
        changed = True
    if not isinstance(tog0, dict):
        changed = True

    num2: Dict[str, float] = {}
    for k, v in num.items():
        try:
            num2[str(k)] = float(v)
        except Exception:
            num2[str(k)] = 0.0
            changed = True

    tog2: Dict[str, bool] = {}
    for k, v in tog.items():
        try:
            tog2[str(k)] = bool(v)
        except Exception:
            tog2[str(k)] = False
            changed = True

    vars2 = dict(vars_dict)
    vars2["number"] = num2
    vars2["toggle"] = tog2

    if not changed and vars0 is vars_dict and num0 is num and tog0 is tog:
        return p, False

    p["variables"] = vars2
    return p, True


def get_variables_state(project: dict) -> Dict[str, Any]:
    """Return the canonical variables dict (best-effort)."""
    try:
        v = (project or {}).get("variables") or {}
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}
