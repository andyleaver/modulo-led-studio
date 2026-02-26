from __future__ import annotations

from pathlib import Path
from typing import Tuple

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw
import json

def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP8266 (FastLED, no audio) target pack (scaffold, audio disabled)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    sel = resolve_requested_backends(ir.project, meta)
    hw = resolve_requested_hw(ir.project, meta)
    aud = resolve_requested_audio_hw(ir.project, meta, sel.get('audio_backend'))

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
            "USE_MSGEQ7": "0",
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
        "Target: esp8266_fastled_noneaudio\n"
        f"LED backend: {sel.get('led_backend')}\n"
        f"Audio backend: {sel.get('audio_backend')} (forced none)\n"
        f"Written: {p}\n"
    )
    return Path(p), report
