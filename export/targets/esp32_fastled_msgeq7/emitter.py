from __future__ import annotations

from pathlib import Path
from typing import Tuple

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, FASTLED_LED_IMPL, NEOPIXELBUS_LED_IMPL_ESP32
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw
import json


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 target pack (scaffold)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"

    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    sel = resolve_requested_backends(ir.project, meta)
    hw = resolve_requested_hw(ir.project, meta)
    aud = resolve_requested_audio_hw(ir.project, meta, sel.get('audio_backend'))

    # Audio backend: this pack can wire MSGEQ7. Any other value disables audio.
    use_msgeq7 = 1 if str(sel.get("audio_backend")).lower() in ("msgeq7", "spectrum_shield", "spectrum") else 0

    # LED backend: FastLED (default) or NeoPixelBus (ESP32-friendly).
    led_backend = str(sel.get("led_backend") or "FastLED").strip().lower()
    led_impl = NEOPIXELBUS_LED_IMPL_ESP32 if led_backend in ("neopixelbus", "neo_pixel_bus", "neobus") else FASTLED_LED_IMPL

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
            "USE_MSGEQ7": str(use_msgeq7),
            "LED_IMPL": led_impl,
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
    report = (
        "Target: esp32_fastled_msgeq7\n"
        f"LED backend: {sel.get('led_backend')}\n"
        f"Audio backend: {sel.get('audio_backend')} (USE_MSGEQ7={use_msgeq7})\n"
        f"Written: {p}\n"
    )
    return Path(p), report
