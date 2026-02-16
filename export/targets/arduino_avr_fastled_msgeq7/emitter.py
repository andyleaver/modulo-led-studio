from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR
from ...arduino_exporter import export_project_validated, FASTLED_LED_IMPL
from ..registry import resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw

MSGEQ7_BLOCK = r'''// --- Spectrum Shield / MSGEQ7 audio (optional) ---
#define MODULA_USE_SPECTRUM_SHIELD 1
// Default pins (change if needed)
#define MSGEQ7_RESET_PIN @@MSGEQ7_RESET_PIN@@
#define MSGEQ7_STROBE_PIN @@MSGEQ7_STROBE_PIN@@
#define MSGEQ7_LEFT_PIN @@MSGEQ7_LEFT_PIN@@
#define MSGEQ7_RIGHT_PIN @@MSGEQ7_RIGHT_PIN@@

static uint16_t g_left[7];
static uint16_t g_right[7];
static float    g_mono[7];
static float    g_energy = 0.0f;

static void msgeq7_setup() {
  pinMode(MSGEQ7_RESET_PIN, OUTPUT);
  pinMode(MSGEQ7_STROBE_PIN, OUTPUT);
  digitalWrite(MSGEQ7_RESET_PIN, LOW);
  digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
}

static void msgeq7_read() {
  digitalWrite(MSGEQ7_RESET_PIN, HIGH);
  delayMicroseconds(2);
  digitalWrite(MSGEQ7_RESET_PIN, LOW);

  float e = 0.0f;
  for (int i=0;i<7;i++){
    digitalWrite(MSGEQ7_STROBE_PIN, LOW);
    delayMicroseconds(30);
    uint16_t L = (uint16_t)analogRead(MSGEQ7_LEFT_PIN);
    uint16_t R = (uint16_t)analogRead(MSGEQ7_RIGHT_PIN);
    digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
    g_left[i]=L; g_right[i]=R;
    float lf = (float)L / 1023.0f;
    float rf = (float)R / 1023.0f;
    float mf = 0.5f*(lf+rf);
    g_mono[i] = mf;
    e += mf;
  }
  g_energy = e / 7.0f;
}

static inline float audio_value(uint8_t src) {
  if (src == 2) return g_energy; // energy
  if (src >= 10 && src <= 16) return g_mono[src-10];
  if (src >= 20 && src <= 26) return (float)g_left[src-20] / 1023.0f;
  if (src >= 30 && src <= 36) return (float)g_right[src-30] / 1023.0f;
  return 0.0f;
}
'''

AUDIO_NONE_BLOCK = r'''// --- Audio disabled ---
static float g_energy = 0.0f;
static void msgeq7_setup() { }
static void msgeq7_read() { g_energy = 0.0f; }
static inline float audio_value(uint8_t /*src*/) { return 0.0f; }
'''



def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """Arduino AVR target pack (FastLED + MSGEQ7)."""
    tpl = Path(__file__).resolve().parent / "arduino_template.ino.tpl"
    if not tpl.exists():
        # Fallback to shared template if target pack doesn't ship its own.
        tpl = Path(__file__).resolve().parents[2] / "arduino_template.ino.tpl"
    
    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    # Prefer resolved values passed from export.emit.emit_project (ensures gating/report matches).
    sel = _kwargs.get("selection") or resolve_requested_backends(ir.project, meta)
    hw = _kwargs.get("hw") or resolve_requested_hw(ir.project, meta)
    aud = _kwargs.get("audio_hw") or resolve_requested_audio_hw(ir.project, meta, sel.get("audio_backend"))

    use_msgeq7 = 1 if str(sel.get('audio_backend') or '').strip().lower() == 'msgeq7' else 0

    p = export_project_validated(
        ir.project,
        out_path,
        template_path=tpl,
        replacements={
            "LED_IMPL": FASTLED_LED_IMPL,
            "DATA_PIN": str(hw.get("data_pin")),
            "LED_TYPE": str(hw.get("led_type")),
            "COLOR_ORDER": str(hw.get("color_order")),
            "LED_BRIGHTNESS": str(hw.get("brightness")),
            "AUDIO_IMPL": (MSGEQ7_BLOCK if str(sel.get("audio_backend") or "").strip().lower()=="msgeq7" else AUDIO_NONE_BLOCK),
            "MSGEQ7_RESET_PIN": str(aud.get("msgeq7_reset_pin", meta.get("default_msgeq7_reset_pin", "5"))),
            "MSGEQ7_STROBE_PIN": str(aud.get("msgeq7_strobe_pin", meta.get("default_msgeq7_strobe_pin", "4"))),
            "MSGEQ7_LEFT_PIN": str(aud.get("msgeq7_left_pin", meta.get("default_msgeq7_left_pin", "A0"))),
            "MSGEQ7_RIGHT_PIN": str(aud.get("msgeq7_right_pin", meta.get("default_msgeq7_right_pin", "A1"))),
        },
    )
    report = (
        "Target: arduino_avr_fastled_msgeq7\n"
        f"LED backend: {sel.get('led_backend')}\n"
        f"Audio backend: {sel.get('audio_backend')} (USE_MSGEQ7={use_msgeq7})\n"
        f"MSGEQ7 pins: reset={aud.get('msgeq7_reset_pin')} strobe={aud.get('msgeq7_strobe_pin')} left={aud.get('msgeq7_left_pin')} right={aud.get('msgeq7_right_pin')}\n"
        f"Written: {p}\n"
    )
    return Path(p), report

