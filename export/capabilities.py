"""Export Target Capability Profiles (Phase C scaffold)

This module defines explicit capabilities for export targets.
It is intentionally conservative and may not be wired everywhere yet.
"""

from __future__ import annotations
from app.project_model import get_surface_spec
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values

from dataclasses import dataclass

@dataclass(frozen=True)
class TargetCapabilities:
    name: str

    # Audio
    supports_audio_msgeq7: bool = False
    supports_stereo: bool = False
    supports_bands: bool = False

    # Modulotion
    supports_modulotion: bool = False  # keep false until implemented

    # General limits
    max_layers_exportable: int = 1

# Conservative defaults
ARDUINO_FASTLED_BASIC = TargetCapabilities(
    name="arduino_fastled_basic",
    supports_audio_msgeq7=False,
    supports_stereo=False,
    supports_bands=False,
    supports_modulotion=False,
    max_layers_exportable=1,
)

ARDUINO_FASTLED_MSGEQ7_STEREO = TargetCapabilities(
    name="arduino_fastled_msgeq7_stereo",
    supports_audio_msgeq7=True,
    supports_stereo=True,
    supports_bands=True,
    supports_modulotion=False,
    max_layers_exportable=1,
)

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
