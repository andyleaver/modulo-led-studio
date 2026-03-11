"""Export preconditions.

This module contains lightweight checks that must pass before generating a sketch.
It is intentionally dependency-free and lives under export/ so runtime never imports tools/.
"""

from __future__ import annotations
from app.project_model import get_surface_spec
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values

from typing import Any, List, Tuple

def check(project: dict) -> Tuple[bool, List[str], List[str]]:
    """Return (ok, problems, warnings).

    Keep this conservative and schema-tolerant:
    - Fail only on conditions that would definitely make export invalid.
    - Everything else is a warning (or handled by deeper validation in the exporter).
    """
    problems: List[str] = []
    warns: List[str] = []

    if not isinstance(project, dict):
        return False, ["Project is not a dict."], []

    spec = get_surface_spec(project)
    kind = str(getattr(spec, "kind", "") or "").strip().lower()
    if kind not in ("strip", "cells"):
        problems.append("project.surface.kind must resolve to strip or cells.")
    else:
        try:
            n_int = int(getattr(spec, "count", 0) or 0)
        except Exception:
            n_int = None
        if n_int is None or n_int <= 0:
            problems.append("project.surface.count must resolve to a positive integer.")
        if kind == "cells":
            try:
                w_int = int(getattr(spec, "width", 0) or 0)
            except Exception:
                w_int = 0
            try:
                h_int = int(getattr(spec, "height", 0) or 0)
            except Exception:
                h_int = 0
            if w_int <= 0 or h_int <= 0:
                problems.append("project.surface width/height must resolve to positive integers for cells surfaces.")

    layers = project.get("layers")
    if layers is None:
        warns.append("No layers present (layers missing). Export will generate an empty sketch.")
    elif not isinstance(layers, list):
        problems.append("layers must be a list.")

    return (len(problems) == 0), problems, warns

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec
#   spec = get_surface_spec(project)
# This prevents preview/export geometry divergence.

# ------------------------------------------------------------------
# All exporters must use SurfaceSpec for geometry truth
# ------------------------------------------------------------------
def _surface_geometry(project):
    spec = _get_surface_spec(project) if "_get_surface_spec" in globals() else get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    return build_surface_geometry_dict(spec, default_kind="strip", default_count=60)


# ------------------------------------------------------------------
# Legacy layout-based geometry access is deprecated.
# Exporters must NOT read project.surface.shape/width/height directly.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------
