from typing import Any, Dict, List, Optional

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def diag_exc(error: Exception, where: str) -> None:
    try:
        if _DIAGS is not None:
            _DIAGS.exception(error, domain="PROJECT", code="PROJECT_NORMALIZE_EXCEPTION", summary=where)
    except Exception:
        pass


def as_int_list(values) -> List[int]:
    out: List[int] = []
    if values is None:
        return out
    if isinstance(values, (list, tuple, set)):
        for value in values:
            try:
                out.append(int(value))
            except Exception as error:
                diag_exc(error, "app/project_normalize_support.py")
    return out


def clamp_indices(indices: List[int], count: Optional[int]) -> List[int]:
    if count is None or count <= 0:
        return sorted(set(index for index in indices if index >= 0))
    return sorted(set(index for index in indices if 0 <= index < count))


def layout_count(project: Dict[str, Any]) -> Optional[int]:
    try:
        from app.project_model import get_surface_count
        count = int(get_surface_count(project) or 0)
        return count if count > 0 else None
    except Exception:
        return None
