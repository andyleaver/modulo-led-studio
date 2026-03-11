from __future__ import annotations

from typing import Any, Dict
from runtime.extensions import register_health_probe

from .registry import diagnose_target_packs

def _probe() -> Dict[str, Any]:
    info = diagnose_target_packs()
    # Keep output compact; UI can show full JSON on demand.
    return {
        "targets_ok": len(info.get("ok") or []),
        "targets_errors": len(info.get("errors") or []),
        "supported": info.get("supported") or [],
        "errors": info.get("errors") or [],
        "sample": (info.get("ok") or [])[:5],
    }

register_health_probe("targets", _probe)

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec
#   spec = get_surface_spec(project)
# This prevents preview/export geometry divergence.

# ------------------------------------------------------------------
# All exporters must use SurfaceSpec for geometry truth
# ------------------------------------------------------------------
def _surface_geometry(project):
    from app.project_model import get_surface_spec
    from core.surface_compat import get_surface_mapping_values

    spec = get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    mapping = get_surface_mapping_values(spec)
    return {
        "kind": spec.kind,
        "width": spec.width,
        "height": spec.height,
        "count": spec.count,
        "mapping": mapping,
        "serpentine": bool(mapping.get("serpentine", False)),
        "flip_x": bool(mapping.get("flip_x", False)),
        "flip_y": bool(mapping.get("flip_y", False)),
        "rotate": int(mapping.get("rotate", 0)),
        "origin": str(mapping.get("origin", "top_left")),
    }

# ------------------------------------------------------------------
# Legacy layout-based geometry access is deprecated.
# Exporters must NOT read project.surface.shape/width/height directly.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------
