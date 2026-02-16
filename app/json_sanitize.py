"""Utilities for making project dicts safe to JSON-serialize.

The Modulo project dictionary is intended to be plain JSON data, but UI code or
future features can accidentally introduce Python object graphs (including
cycles). That breaks ``json.dumps`` and can cascade into preview-engine rebuild
failures.

This module provides a conservative sanitizer:

* Preserves normal JSON types (dict/list/str/int/float/bool/None).
* Converts unknown objects to a descriptive string.
* Breaks reference cycles by replacing repeated containers with a marker.

It also returns a list of "issues" describing what was changed and where,
useful for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class SanitizeIssue:
    kind: str  # 'cycle' | 'non_json'
    path: str
    note: str


_JSON_SCALARS = (str, int, float, bool, type(None))


def sanitize_for_json(obj: Any, *, max_depth: int = 128) -> Tuple[Any, List[SanitizeIssue]]:
    """Return (sanitized_obj, issues).

    The output is safe for ``json.dumps``.
    """

    issues: List[SanitizeIssue] = []
    seen: Dict[int, str] = {}

    def rec(x: Any, path: str, depth: int) -> Any:
        if depth > max_depth:
            issues.append(SanitizeIssue("non_json", path, f"max_depth>{max_depth}"))
            return "<DEPTH_LIMIT>"

        if isinstance(x, _JSON_SCALARS):
            return x

        # Containers
        if isinstance(x, dict):
            oid = id(x)
            if oid in seen:
                issues.append(SanitizeIssue("cycle", path, f"dict cycle -> {seen[oid]}"))
                return "<CYCLE:dict>"
            seen[oid] = path
            out: Dict[str, Any] = {}
            for k, v in x.items():
                # JSON requires string keys; keep best-effort.
                ks = k if isinstance(k, str) else repr(k)
                out[ks] = rec(v, f"{path}.{ks}" if path else ks, depth + 1)
            return out

        if isinstance(x, (list, tuple)):
            oid = id(x)
            if oid in seen:
                issues.append(SanitizeIssue("cycle", path, f"list cycle -> {seen[oid]}"))
                return "<CYCLE:list>"
            seen[oid] = path
            out_list = [rec(v, f"{path}[{i}]", depth + 1) for i, v in enumerate(x)]
            return out_list

        # Unknown object: stringify.
        issues.append(SanitizeIssue("non_json", path, f"{type(x).__name__}"))
        try:
            return repr(x)
        except Exception:
            return f"<{type(x).__name__}>"

    return rec(obj, "", 0), issues
