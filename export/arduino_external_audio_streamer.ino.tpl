/*
  Modulo External Audio Streamer (MSGEQ7 / Spectrum Shield)
  Sends key=value frames over Serial for Modulo preview "external" mode.

  Output format (one line per frame):
    energy=0.123 mono0=0.45 mono1=... mono6=... l0=...l6=... r0=...r6=...

  Notes:
  - Values are 0..1 floats (3 decimal places).
  - Set pins to match your wiring.
*/

#include <Arduino.h>

#define MSGEQ7_RESET_PIN @@MSGEQ7_RESET_PIN@@
#define MSGEQ7_STROBE_PIN @@MSGEQ7_STROBE_PIN@@
#define MSGEQ7_LEFT_PIN @@MSGEQ7_LEFT_PIN@@
#define MSGEQ7_RIGHT_PIN @@MSGEQ7_RIGHT_PIN@@

static uint16_t leftRaw[7];
static uint16_t rightRaw[7];
static float mono[7];
static float energy = 0.0f;

static inline float clamp01(float x){ return (x<0)?0:((x>1)?1:x); }

static void msgeq7_setup(){
  pinMode(MSGEQ7_RESET_PIN, OUTPUT);
  pinMode(MSGEQ7_STROBE_PIN, OUTPUT);
  digitalWrite(MSGEQ7_RESET_PIN, LOW);
  digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
}

static void msgeq7_read(){
  digitalWrite(MSGEQ7_RESET_PIN, HIGH);
  delayMicroseconds(2);
  digitalWrite(MSGEQ7_RESET_PIN, LOW);

  float e = 0.0f;
  for(int i=0;i<7;i++){
    digitalWrite(MSGEQ7_STROBE_PIN, LOW);
    delayMicroseconds(30);
    uint16_t L = (uint16_t)analogRead(MSGEQ7_LEFT_PIN);
    uint16_t R = (uint16_t)analogRead(MSGEQ7_RIGHT_PIN);
    digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
    leftRaw[i]=L; rightRaw[i]=R;
    float lf = (float)L / 1023.0f;
    float rf = (float)R / 1023.0f;
    float mf = 0.5f*(lf+rf);
    mono[i] = clamp01(mf);
    e += mono[i];
  }
  energy = clamp01(e / 7.0f);
}

void setup(){
  Serial.begin(115200);
  msgeq7_setup();
}

void loop(){
  msgeq7_read();

  Serial.print("energy="); Serial.print(energy, 3);
  for(int i=0;i<7;i++){ Serial.print(" mono"); Serial.print(i); Serial.print("="); Serial.print(mono[i], 3); }
  for(int i=0;i<7;i++){ Serial.print(" l"); Serial.print(i); Serial.print("="); Serial.print(((float)leftRaw[i]/1023.0f), 3); }
  for(int i=0;i<7;i++){ Serial.print(" r"); Serial.print(i); Serial.print("="); Serial.print(((float)rightRaw[i]/1023.0f), 3); }
  Serial.println();

  delay(20); // ~50 fps
}
