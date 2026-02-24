from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, FASTLED_LED_IMPL, NEOPIXELBUS_LED_IMPL
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw


def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """ESP32 target pack supporting FastLED or NeoPixelBus (strip+matrix). Emits a single .ino sketch."""
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

    led_backend_raw = str(sel.get("led_backend") or "").strip() or "NeoPixelBus"
    led_backend = led_backend_raw.lower()
    led_impl = FASTLED_LED_IMPL
    if led_backend in ("neopixelbus", "neo_pixel_bus", "neopixel_bus"):
        led_impl = NEOPIXELBUS_LED_IMPL
    elif led_backend == "fastled":
        led_impl = FASTLED_LED_IMPL
    else:
        raise RuntimeError(f"Unsupported led_backend for ESP32 target: {led_backend_raw}")

    use_msgeq7 = 1 if str(sel.get("audio_backend") or "").strip().lower() == "msgeq7" else 0

    # AUDIO_BLOCK is injected into the template. When audio is disabled, the block must omit any MSGEQ7_* tokens/strings.
    if use_msgeq7:
        audio_block_lines = [
            "// --- Spectrum Shield / MSGEQ7 audio ---",
            "#define USE_MSGEQ7 1",
            f"#define MSGEQ7_RESET_PIN {aud.get('msgeq7_reset_pin')}",
            f"#define MSGEQ7_STROBE_PIN {aud.get('msgeq7_strobe_pin')}",
            f"#define MSGEQ7_LEFT_PIN {aud.get('msgeq7_left_pin')}",
            f"#define MSGEQ7_RIGHT_PIN {aud.get('msgeq7_right_pin')}",
            "",
            "static uint16_t g_left[7];",
            "static uint16_t g_right[7];",
            "static float    g_mono[7];",
            "static float    g_energy = 0.0f;",
            "",
            "static void msgeq7_setup() {",
            "  pinMode(MSGEQ7_RESET_PIN, OUTPUT);",
            "  pinMode(MSGEQ7_STROBE_PIN, OUTPUT);",
            "  digitalWrite(MSGEQ7_RESET_PIN, LOW);",
            "  digitalWrite(MSGEQ7_STROBE_PIN, HIGH);",
            "}",
            "",
            "static void msgeq7_read() {",
            "  digitalWrite(MSGEQ7_RESET_PIN, HIGH);",
            "  delayMicroseconds(2);",
            "  digitalWrite(MSGEQ7_RESET_PIN, LOW);",
            "",
            "  float e = 0.0f;",
            "  for (int i=0;i<7;i++){",
            "    digitalWrite(MSGEQ7_STROBE_PIN, LOW);",
            "    delayMicroseconds(30);",
            "    uint16_t L = (uint16_t)analogRead(MSGEQ7_LEFT_PIN);",
            "    uint16_t R = (uint16_t)analogRead(MSGEQ7_RIGHT_PIN);",
            "    digitalWrite(MSGEQ7_STROBE_PIN, HIGH);",
            "    g_left[i]=L; g_right[i]=R;",
            "    float lf = (float)L / 1023.0f;",
            "    float rf = (float)R / 1023.0f;",
            "    float mf = 0.5f*(lf+rf);",
            "    g_mono[i] = mf;",
            "    e += mf;",
            "  }",
            "  g_energy = e / 7.0f;",
            "}",
            "",
            "static inline float audio_value(uint8_t src) {",
            "  if (src == 2) return g_energy; // energy",
            "  if (src >= 10 && src <= 16) return g_mono[src-10];",
            "  if (src >= 20 && src <= 26) return (float)g_left[src-20] / 1023.0f;",
            "  if (src >= 30 && src <= 36) return (float)g_right[src-30] / 1023.0f;",
            "  return 0.0f;",
            "}",
        ]
    else:
        audio_block_lines = [
            "// --- Audio disabled ---",
            "static void msgeq7_setup() { }",
            "static void msgeq7_read() { }",
            "static inline float audio_value(uint8_t src) { (void)src; return 0.0f; }",
        ]
    audio_block = "\n".join(audio_block_lines) + "\n"


    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
            "USE_MSGEQ7": str(use_msgeq7),
            "LED_IMPL": led_impl,
            "AUDIO_BLOCK": audio_block,
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
        "Target: esp32_neopixelbus_msgeq7\n"
        f"LED backend: {led_backend}\n"
        f"Audio backend: {sel.get('audio_backend')}\n"
        f"Written: {p}\n"
    )

    om = str(_kwargs.get("output_mode") or "").strip().lower()
    if om.startswith("platformio"):
        proj_dir = out_path.parent / (out_path.stem + "_pio")
        src_dir = proj_dir / "src"
        include_dir = proj_dir / "include"
        src_dir.mkdir(parents=True, exist_ok=True)
        include_dir.mkdir(parents=True, exist_ok=True)

        main_cpp = src_dir / "main.cpp"
        try:
            ino_txt = Path(p).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            ino_txt = ""
        main_cpp.write_text(ino_txt.rstrip() + "\n", encoding="utf-8")

        ini = proj_dir / "platformio.ini"
        # Build lib_deps based on selected LED backend
        backend = str((sel or {}).get("led_backend") or "").strip().lower()
        deps = []
        if ("neopixelbus" in backend) or (not backend):
            deps.append("  makuna/NeoPixelBus@^2.7.0")
        if "fastled" in backend:
            deps.append("  fastled/FastLED@^3.6.0")
        if not deps:
            # Default for this target: NeoPixelBus
            deps.append("  makuna/NeoPixelBus@^2.7.0")
        ini_text = "[env:esp32dev]\n"
        ini_text += "platform = espressif32\n"
        ini_text += "board = esp32dev\n"
        ini_text += "framework = arduino\n"
        ini_text += "lib_deps =\n"
        ini_text += "\n".join(deps) + "\n"
        ini.write_text(ini_text, encoding="utf-8")

        (proj_dir / "README.txt").write_text(
            "PlatformIO export. Open this folder in VS Code + PlatformIO and Build/Upload.\n",
            encoding="utf-8"
        )

        report = report + "\nPlatformIO project: " + str(proj_dir) + "\n"
        return proj_dir, report

    return Path(p), report
