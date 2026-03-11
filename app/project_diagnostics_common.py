from __future__ import annotations

from typing import Any, Dict, Optional, Set

from app.project_model import get_surface_snapshot

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="PROJECT_DIAGNOSTICS_EXCEPTION", summary=where)
    except Exception:
        pass


def _layout_count(project: Dict[str, Any]) -> Optional[int]:
    try:
        snap = get_surface_snapshot(project if isinstance(project, dict) else {})
        n = int((snap or {}).get("count") or 0)
        return n if n > 0 else None
    except Exception:
        return None


def _collect_mask_refs(node: Any, out: Set[str]) -> None:
    """Collect string mask references used inside a mask node."""
    try:
        if isinstance(node, str):
            out.add(node)
            return
        if isinstance(node, dict):
            a = node.get("a")
            b = node.get("b")
            if a is not None:
                _collect_mask_refs(a, out)
            if b is not None:
                _collect_mask_refs(b, out)
            return
    except Exception:
        return
