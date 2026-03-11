"""Signal key -> Arduino C++ expression map (Phase C.9 groundwork)

Purpose:
- Provide a single source of truth mapping for exportable signal keys
  to the Arduino variables/functions generated in the template.

Notes:
- This module is *not* yet used by all behavior emitters; it is a building block.
- Audio variables expected to exist when MODULA_USE_SPECTRUM_SHIELD is enabled:
    g_energy (0..1023*7 clamped), g_peak
    g_mono[7], g_left[7], g_right[7]
"""

from __future__ import annotations
from app.project_model import get_surface_spec
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values

from typing import Optional

def arduino_expr_for_signal(key: str) -> Optional[str]:
    """Return Arduino C++ expression for a signal key, or None if unknown."""
    if not isinstance(key, str) or not key:
        return None

    k = key.strip()

    # Energy/peak
    if k == "audio_energy":
        return "g_energy"
    if k == "audio_peak":
        return "g_peak"

    # Bands
    # mono
    if k.startswith("audio_mono_"):
        idx = _parse_band_index(k, "audio_mono_")
        return None if idx is None else f"g_mono[{idx}]"
    # left
    if k.startswith("audio_left_"):
        idx = _parse_band_index(k, "audio_left_")
        return None if idx is None else f"g_left[{idx}]"
    # right
    if k.startswith("audio_right_"):
        idx = _parse_band_index(k, "audio_right_")
        return None if idx is None else f"g_right[{idx}]"

    return None

def _parse_band_index(key: str, prefix: str) -> Optional[int]:
    try:
        s = key[len(prefix):]
        i = int(s)
        if 0 <= i <= 6:
            return i
    except Exception:
        return None
    return None

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
