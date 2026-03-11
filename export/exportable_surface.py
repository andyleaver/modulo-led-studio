"""Exportable Surface Schema

This module is the *single source of truth* for what the app considers
"exportable".

Goal: prevent preview-only authoring from accidentally producing projects that
cannot export.

Use this from:
- Export validation (fail-closed)
- UI widgets (offer only exportable options by default)
"""

from __future__ import annotations
from app.project_model import get_surface_spec
from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values

from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class ExportableSurface:
    """A minimal, machine-readable exportable surface description."""

    # Rules: allowed params for action.kind == "set_layer_param"
    rules_layer_params: List[str]

    # Exportable operator kinds (runtime exists on targets that opt-in)
    operators_kinds: List[str]

    # PostFX keys exposed for export/runtime (project.postfx)
    postfx_keys: List[str]

    # Modulotion: target keys that are safe/exportable (layer.modulotors target)
    modulotion_targets: List[str]

    # Modulotion: source keys that are safe/exportable (layer.modulotors source)
    modulotion_sources: List[str]

# ---- Canonical exportable surface

RULES_LAYER_PARAMS_EXPORTABLE: List[str] = [
    # Layer params
    "opacity",
    "brightness",
    # Operators (canonical runtime addresses)
    "operator.gain",
    "operator.gamma",
    "operator.posterize_levels",
    # PostFX (canonical runtime addresses)
    "project.postfx.trail_amount",
    "project.postfx.bleed_amount",
    "project.postfx.bleed_radius",
]

OPERATORS_KINDS_EXPORTABLE: List[str] = [
    "gain",
    "gamma",
    "posterize",
]

POSTFX_KEYS_EXPORTABLE: List[str] = [
    "trail",
    "bleed",
]

# Note: modulotion targets are referenced by stable "purpose" ids in export.
# Keep this list conservative; expand only with fixtures.
MODULATION_TARGETS_EXPORTABLE: List[str] = [
    "speed",
    "brightness",
    "width",
    "softness",
    "density",
    # Purpose channels
    "purpose_f0",
    "purpose_f1",
    "purpose_f2",
    "purpose_f3",
]

# Modulotion sources supported by runtime/export. Keep aligned with params.registry.SOURCES
MODULATION_SOURCES_EXPORTABLE: List[str] = [
    "none",
    "lfo_sine",
    "audio_energy",
    "audio_mono0","audio_mono1","audio_mono2","audio_mono3","audio_mono4","audio_mono5","audio_mono6",
    "audio_L0","audio_L1","audio_L2","audio_L3","audio_L4","audio_L5","audio_L6",
    "audio_R0","audio_R1","audio_R2","audio_R3","audio_R4","audio_R5","audio_R6",
    "audio_beat","audio_kick","audio_snare","audio_onset","audio_bpm","audio_bpm_conf","audio_sec_change","audio_sec_id",
    "audio_tr_L0","audio_tr_L1","audio_tr_L2","audio_tr_L3","audio_tr_L4","audio_tr_L5","audio_tr_L6",
    "audio_tr_R0","audio_tr_R1","audio_tr_R2","audio_tr_R3","audio_tr_R4","audio_tr_R5","audio_tr_R6",
    "audio_pk_L0","audio_pk_L1","audio_pk_L2","audio_pk_L3","audio_pk_L4","audio_pk_L5","audio_pk_L6",
    "audio_pk_R0","audio_pk_R1","audio_pk_R2","audio_pk_R3","audio_pk_R4","audio_pk_R5","audio_pk_R6",
    "purpose_f0","purpose_f1","purpose_f2","purpose_f3",
]

SURFACE = ExportableSurface(
    rules_layer_params=RULES_LAYER_PARAMS_EXPORTABLE,
    operators_kinds=OPERATORS_KINDS_EXPORTABLE,
    postfx_keys=POSTFX_KEYS_EXPORTABLE,
    modulotion_targets=MODULATION_TARGETS_EXPORTABLE,
    modulotion_sources=MODULATION_SOURCES_EXPORTABLE,
)

def surface_schema() -> Dict[str, List[str]]:
    """Return a JSON-serializable canonical exportable-surface view."""

    return {
        "rules.set_layer_param": list(SURFACE.rules_layer_params),
        "operators.kinds": list(SURFACE.operators_kinds),
        "postfx.keys": list(SURFACE.postfx_keys),
        "modulotion.targets": list(SURFACE.modulotion_targets),
        "modulotion.sources": list(SURFACE.modulotion_sources),
    }

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


def surface_matrix() -> Dict[str, List[str]]:
    """Compatibility wrapper for older callers still using matrix wording."""
    return surface_schema()
