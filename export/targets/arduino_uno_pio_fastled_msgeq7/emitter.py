from __future__ import annotations
from pathlib import Path
from typing import Tuple
from app.project_model import get_surface_spec

from ...ir import ShowIR
from ..arduino_uno_fastled_msgeq7.emitter import emit as _emit_ino

def emit(*, ir: ShowIR, out_path: Path, **kwargs) -> Tuple[Path, str]:
    """Arduino Uno (PlatformIO + FastLED + MSGEQ7) PlatformIO project emitter."""
    ino_path, rep = _emit_ino(ir=ir, out_path=out_path, **kwargs)

    proj_dir = out_path.parent / (out_path.stem + "_pio")
    src_dir = proj_dir / "src"
    include_dir = proj_dir / "include"
    src_dir.mkdir(parents=True, exist_ok=True)
    include_dir.mkdir(parents=True, exist_ok=True)

    main_cpp = src_dir / "main.cpp"
    try:
        txt = ino_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ""
    main_cpp.write_text(txt.rstrip() + "\n", encoding="utf-8")

    ini = proj_dir / "platformio.ini"
    ini.write_text("""[env:modulo]
platform = atmelavr
board = uno
framework = arduino
lib_deps =
  fastled/FastLED@^3.6.0
""".rstrip() + "\n", encoding="utf-8")

    (proj_dir / "README.txt").write_text(
        "PlatformIO export. Open this folder in VS Code + PlatformIO and Build/Upload.\n",
        encoding="utf-8"
    )

    report = rep + "\nPlatformIO project: " + str(proj_dir) + "\n"
    return proj_dir, report

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
