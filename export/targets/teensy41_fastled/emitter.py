from __future__ import annotations
from app.project_model import get_surface_spec

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR

def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """Placeholder Teensy target.

    This exists to prove the 'one engine, many targets' path:
    - capability profile is real
    - parity gates can evaluate against this target
    - emitter is intentionally blocked until we implement a real backend
    """
    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    raise RuntimeError(
        "Target 'teensy41_fastled' is a placeholder pack: gating works, but emitting is not implemented yet. "
        "Choose 'arduino_avr_fastled_msgeq7' for real exports."
    )

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
