from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, FASTLED_LED_IMPL
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """RP2040 Pico target pack (MVP uses FastLED). Emits a single .ino sketch."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    if not tpl.exists():
        tpl = Path(__file__).resolve().parents[2] / "arduino_template.ino.tpl"

    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    sel = _kwargs.get("selection") or resolve_requested_backends(ir.project, meta)
    hw = _kwargs.get("hw") or resolve_requested_hw(ir.project, meta)
    aud = _kwargs.get("audio_hw") or resolve_requested_audio_hw(ir.project, meta, sel.get("audio_backend"))

    led_backend = str(sel.get("led_backend") or "").strip()
    if led_backend and led_backend.strip().lower() != 'fastled':
        raise RuntimeError("rp2040_pico_fastled_msgeq7 MVP currently supports led_backend=FastLED only.")

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
    out_mode = str(_kwargs.get("output_mode") or "").strip().lower()
    if out_mode.startswith("platformio") or out_mode in ("pio", "pio_zip"):
        proj_dir = out_path.parent / (out_path.stem + "_pio")
        src_dir = proj_dir / "src"
        include_dir = proj_dir / "include"
        src_dir.mkdir(parents=True, exist_ok=True)
        include_dir.mkdir(parents=True, exist_ok=True)

        main_cpp = src_dir / "main.cpp"
        try:
            txt = Path(p).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            txt = ""
        main_cpp.write_text(txt.rstrip() + "\n", encoding="utf-8")

        ini = proj_dir / "platformio.ini"
        ini.write_text(
            """[env:pico]
platform = raspberrypi
board = pico
framework = arduino
lib_deps =
  fastled/FastLED@^3.6.0
""".rstrip() + "\n",
            encoding="utf-8"
        )
        (proj_dir / "README.txt").write_text(
            "PlatformIO export. Open this folder in VS Code + PlatformIO and Build/Upload.\n",
            encoding="utf-8"
        )

        # Return the folder; export.emit will zip it for platformio output_mode.
        p = proj_dir

    report = (
        "Target: rp2040_pico_fastled_msgeq7 (MVP FastLED)\n"
        f"LED backend: {sel.get('led_backend')}\n"
        f"Audio backend: {sel.get('audio_backend')} (USE_MSGEQ7={use_msgeq7})\n"
        f"Written: {p}\n"
    )
    return Path(p), report
