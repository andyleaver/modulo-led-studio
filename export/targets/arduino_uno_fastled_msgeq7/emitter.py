from __future__ import annotations
from pathlib import Path
from typing import Tuple
from ...ir import ShowIR
from ..arduino_avr_fastled_msgeq7.emitter import emit as _emit_avr

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


def emit(*, ir: ShowIR, out_path: Path, **kwargs) -> Tuple[Path, str]:
    """Arduino Uno (FastLED + MSGEQ7) wrapper around AVR FastLED+MSGEQ7 emitter."""
    return _emit_avr(ir=ir, out_path=out_path, **kwargs)

