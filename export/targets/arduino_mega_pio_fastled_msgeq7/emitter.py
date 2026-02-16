from __future__ import annotations
from pathlib import Path
from typing import Tuple

from ...ir import ShowIR
from ..arduino_mega_fastled_msgeq7.emitter import emit as _emit_ino

def emit(*, ir: ShowIR, out_path: Path, **kwargs) -> Tuple[Path, str]:
    """Arduino Mega (PlatformIO + FastLED + MSGEQ7) PlatformIO project emitter."""
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
board = megaatmega2560
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
