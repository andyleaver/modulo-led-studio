"""Utilities for storing modulation specs in project data.

Modulo stores modulators as JSON-serializable dict specs. The PreviewEngine
normalizes those specs into runtime modulators when a project is loaded.
"""

from __future__ import annotations

from typing import Any, Dict

def build_modulotor(spec: Any) -> Dict[str, Any]:
    """Return a dict spec suitable for storage in project data.

    Modulo's current modulation pipeline stores modulotors as dict specs (JSON-serializable).
    The PreviewEngine is responsible for normalizing these specs into runtime modulotor objects.
    """
    if spec is None:
        return {}
    if isinstance(spec, dict):
        return dict(spec)
    raise TypeError(f"Unsupported modulotor spec type: {type(spec).__name__}")
