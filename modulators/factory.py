"""Legacy wrapper for Modulo's modulation system.

The canonical modulotor runtime implementation currently lives inside the PreviewEngine
(`preview.preview_engine._normalize_modulotors` + runtime application).

This module exists purely for import stability across refactors.
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
