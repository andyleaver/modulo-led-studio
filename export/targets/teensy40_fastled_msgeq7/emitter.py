from __future__ import annotations
from pathlib import Path
from typing import Tuple
import json
from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, FASTLED_LED_IMPL
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw
def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """Teensy 4.0 target pack (FastLED + MSGEQ7). Emits a single .ino sketch."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    if not tpl.exists():
        tpl = Path(__file__).resolve().parents[2] / "arduino_template.ino.tpl"
    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    # Prefer resolved values passed from export.emit.emit_project
    sel = _kwargs.get("selection") or resolve_requested_backends(ir.project, meta)
    hw = _kwargs.get("hw") or resolve_requested_hw(ir.project, meta)
    aud = _kwargs.get("audio_hw") or resolve_requested_audio_hw(ir.project, meta, sel.get("audio_backend"))
    use_msgeq7 = 1 if str(sel.get("audio_backend") or "").strip().lower() == "msgeq7" else 0
    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
            "USE_MSGEQ7": str(use_msgeq7),
            "LED_IMPL": FASTLED_LED_IMPL,
            "DATA_PIN": str(hw.get("data_pin")),
            "LED_TYPE": str(hw.get("led_type")),
            "COLOR_ORDER": str(hw.get("color_order")),
            "LED_BRIGHTNESS": str(hw.get("brightness")),
            "MSGEQ7_RESET_PIN": str(aud.get("msgeq7_reset_pin", meta.get("default_msgeq7_reset_pin", "5"))),
            "MSGEQ7_STROBE_PIN": str(aud.get("msgeq7_strobe_pin", meta.get("default_msgeq7_strobe_pin", "4"))),
            "MSGEQ7_LEFT_PIN": str(aud.get("msgeq7_left_pin", meta.get("default_msgeq7_left_pin", "A0"))),
            "MSGEQ7_RIGHT_PIN": str(aud.get("msgeq7_right_pin", meta.get("default_msgeq7_right_pin", "A1"))),
        },
    )
    # If PlatformIO output is requested, wrap the emitted sketch in a PlatformIO project folder.
    out_mode = str(_kwargs.get("output_mode") or (ir.project.get("export") or {}).get("output_mode") or "").strip().lower()
    if out_mode == "platformio":
        txt = Path(p).read_text(encoding="utf-8")
        proj_dir = out_path.with_suffix("")
        proj_dir.mkdir(parents=True, exist_ok=True)
        src = proj_dir / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "main.cpp").write_text(txt, encoding="utf-8")
        ini = proj_dir / "platformio.ini"
        ini.write_text("""[env:modulo]
platform = teensy
board = teensy40
framework = arduino
lib_deps =
  fastled/FastLED@^3.6.0
""".rstrip() + "\n", encoding="utf-8")
        p = proj_dir
    report = (
        "Target: teensy40_fastled_msgeq7\n"
        f"LED backend: {sel.get('led_backend')}\n"
        f"Audio backend: {sel.get('audio_backend')} (USE_MSGEQ7={use_msgeq7})\n"
        f"Written: {p}\n"
    )
    return Path(p), report
