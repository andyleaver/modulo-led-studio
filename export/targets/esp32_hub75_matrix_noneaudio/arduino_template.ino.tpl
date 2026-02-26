// --- MODULA EXPORT TARGET: ESP32 (FastLED + MSGEQ7) ---
// Notes:
// - ESP32 analogRead() is typically 0..4095 (12-bit) unless configured differently.
// - Default ADC pins differ by board; GPIO34/35 are common input-only ADC pins on DevKit boards.
// - If you use a real Spectrum Shield, you may need a level shift or different wiring.
// - Validate pins and analog scaling for your specific ESP32 board/core version.

#define MODULA_USE_SPECTRUM_SHIELD @@USE_MSGEQ7@@

// Default pins (change if needed)
#define MSGEQ7_RESET_PIN @@MSGEQ7_RESET_PIN@@
#define MSGEQ7_STROBE_PIN @@MSGEQ7_STROBE_PIN@@
#define MSGEQ7_LEFT_PIN @@MSGEQ7_LEFT_PIN@@
#define MSGEQ7_RIGHT_PIN @@MSGEQ7_RIGHT_PIN@@

#ifndef MODULA_ADC_MAX
#define MODULA_ADC_MAX 4095.0f
#endif

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
#if MODULA_USE_SPECTRUM_SHIELD
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

    float lf = (float)L / MODULA_ADC_MAX;
    float rf = (float)R / MODULA_ADC_MAX;
    float mf = 0.5f*(lf+rf);
    g_mono[i] = mf;
    e += mf;
  }
  g_energy = e / 7.0f;
#else
  g_energy = 0.0f;
  for(int i=0;i<7;i++){ g_left[i]=0; g_right[i]=0; g_mono[i]=0.0f; }
#endif
}

static inline float audio_value(uint8_t src) {
  if (src == 2) return g_energy; // energy
  if (src >= 10 && src <= 16) return g_mono[src-10];
  if (src >= 20 && src <= 26) return (float)g_left[src-20] / MODULA_ADC_MAX;
  if (src >= 30 && src <= 36) return (float)g_right[src-30] / MODULA_ADC_MAX;
  return 0.0f;
}

@@SKETCH@@
