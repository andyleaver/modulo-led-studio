

// --- Modulo wiring / LED config ---
#define LED_PIN @@DATA_PIN@@
#define LED_TYPE @@LED_TYPE@@
#define COLOR_ORDER @@COLOR_ORDER@@
#define LED_BRIGHTNESS @@LED_BRIGHTNESS@@
#define USE_MSGEQ7 @@USE_MSGEQ7@@


@@AUDIO_IMPL@@
// --- LED backend implementation ---
@@LED_IMPL@@

// --- Matrix implementation (if applicable) ---
@@MATRIX_IMPL@@

@@SKETCH@@

