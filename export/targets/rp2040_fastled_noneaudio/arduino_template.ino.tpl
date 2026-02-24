// --- MODULA EXPORT TARGET: RP2040 (FastLED, no audio) ---
// Notes:
// - Intended for RP2040-class boards (e.g., Raspberry Pi Pico / Pico W).
// - Audio sources export as 0.0 (disabled). If you want audio on RP2040, add an audio backend pack.

#define MODULA_USE_SPECTRUM_SHIELD @@USE_MSGEQ7@@

static uint16_t g_left[7];
static uint16_t g_right[7];
static float    g_mono[7];
static float    g_energy = 0.0f;

static void msgeq7_setup() {
  // audio disabled
}

static void msgeq7_read() {
  g_energy = 0.0f;
  for(int i=0;i<7;i++){ g_left[i]=0; g_right[i]=0; g_mono[i]=0.0f; }
}

static inline float audio_value(uint8_t src) {
  (void)src;
  return 0.0f;
}

@@SKETCH@@
