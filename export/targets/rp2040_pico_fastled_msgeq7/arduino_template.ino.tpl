

// --- Spectrum Shield / MSGEQ7 audio (optional) ---
// Compatibility define
#define USE_MSGEQ7 @@USE_MSGEQ7@@
#define MODULA_USE_SPECTRUM_SHIELD @@USE_MSGEQ7@@
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
    float lf = (float)L / 1023.0f;
    float rf = (float)R / 1023.0f;
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
  if (src >= 20 && src <= 26) return (float)g_left[src-20] / 1023.0f;
  if (src >= 30 && src <= 36) return (float)g_right[src-30] / 1023.0f;
  return 0.0f;
}


// --- LED backend implementation ---
@@LED_IMPL@@

// --- Matrix implementation (if applicable) ---
@@MATRIX_IMPL@@

@@SKETCH@@
