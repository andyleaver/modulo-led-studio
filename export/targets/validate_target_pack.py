from __future__ import annotations

from typing import Any, Dict, List, Tuple

def validate_target_pack(meta: Any) -> Tuple[bool, List[str]]:
    """
    Validate a loaded target.json meta dict (structural).
    Supports both legacy and current schemas.

    Required:
      - id (str)
      - name (str)
      - capabilities (dict)
      - emitter module path key: 'emitter' OR 'emitter_module'
    """
    errors: List[str] = []
    if not isinstance(meta, dict):
        return False, ["target meta is not dict"]

    def _req_str(k: str) -> None:
        v = meta.get(k)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"missing or invalid key: {k}")

    _req_str("id")
    _req_str("name")

    caps = meta.get("capabilities")
    if not isinstance(caps, dict):
        errors.append("missing or invalid key: capabilities (dict required)")

    em = meta.get("emitter") or meta.get("emitter_module")
    if not isinstance(em, str) or not em.strip():
        errors.append("missing emitter (expected 'emitter' or 'emitter_module')")

    # Optional: platformio if present must be dict
    pio = meta.get("platformio")
    if pio is not None and not isinstance(pio, dict):
        errors.append("platformio must be dict if present")

    return (len(errors) == 0), errors

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
