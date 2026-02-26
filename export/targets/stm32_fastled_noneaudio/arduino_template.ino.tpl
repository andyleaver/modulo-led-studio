// --- MODULA EXPORT TARGET: STM32 (FastLED, no audio) ---
// Notes:
// - Scaffold target pack.
// - Audio disabled (all audio sources export as 0.0).
// - Validate LED pin/output method for your specific board.

#define MODULA_USE_SPECTRUM_SHIELD @@USE_MSGEQ7@@

static uint16_t g_left[7];
static uint16_t g_right[7];
static float    g_mono[7];
static float    g_energy = 0.0f;

static void msgeq7_setup() {}
static void msgeq7_read() {
  g_energy = 0.0f;
  for(int i=0;i<7;i++){ g_left[i]=0; g_right[i]=0; g_mono[i]=0.0f; }
}
static inline float audio_value(uint8_t src) { (void)src; return 0.0f; }

@@SKETCH@@
