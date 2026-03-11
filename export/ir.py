from __future__ import annotations
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values
from app.project_model import get_surface_snapshot, get_surface_spec

from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class ShowIR:
    """
    Target-neutral intermediate representation (bootstrap).

    For now it holds:
      - the validated project dict
      - resolved selection/hw/audio_hw
      - convenience fields for surface/layers
    """
    project: Dict[str, Any]
    selection: Dict[str, Any]
    hw: Dict[str, Any]
    audio_hw: Dict[str, Any]
    surface: Dict[str, Any]
    layers: List[Dict[str, Any]]

    # Live export truth is ``surface`` only.

    @staticmethod
    def from_project(project: Dict[str, Any], selection: Dict[str, Any], hw: Dict[str, Any], audio_hw: Dict[str, Any]) -> "ShowIR":
        project = project or {}
        return ShowIR(
            project=project,
            selection=selection or {},
            hw=hw or {},
            audio_hw=audio_hw or {},
            surface=get_surface_snapshot(project),
            layers=list(project.get("layers") or []),
        )

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_snapshot, get_surface_spec
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
# Exporters should consume canonical surface helpers/SurfaceSpec.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------
