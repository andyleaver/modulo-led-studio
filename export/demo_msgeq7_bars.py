"""Standalone MSGEQ7 + FastLED demo sketch generator (Phase C.11)

This does NOT depend on Modulo layer emitters.
It's a known-good exported .ino to validate:
- pins
- MSGEQ7 reads
- FastLED output

The sketch draws 7 bars across the strip based on mono bands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    led_count: int = 575
    data_pin: int = 6
    strobe_pin: int = 4
    reset_pin: int = 5
    left_pin: str = "A0"
    right_pin: str = "A1"
    brightness: int = 128
    noise_floor: int = 60
    gain: float = 1.0
    strobe_delay_us: int = 30


def make_demo_sketch(cfg: DemoConfig) -> str:
    # Keep it single-file and Arduino-IDE friendly.
    return f"""    #include <FastLED.h>

// ---- LED strip ----
#define LED_PIN {cfg.data_pin}
#define LED_COUNT {int(cfg.led_count)}
#define BRIGHTNESS {int(cfg.brightness)}
CRGB leds[LED_COUNT];

// ---- MSGEQ7 (Spectrum Shield stereo) ----
#define MSGEQ7_STROBE_PIN {cfg.strobe_pin}
#define MSGEQ7_RESET_PIN {cfg.reset_pin}
#define MSGEQ7_LEFT_PIN {cfg.left_pin}
#define MSGEQ7_RIGHT_PIN {cfg.right_pin}

uint16_t bandL[7];
uint16_t bandR[7];
uint16_t bandM[7];

static inline uint16_t clamp1023(int v) {{
  if (v < 0) return 0;
  if (v > 1023) return 1023;
  return (uint16_t)v;
}}

void msgeq7_setup() {{
  pinMode(MSGEQ7_RESET_PIN, OUTPUT);
  pinMode(MSGEQ7_STROBE_PIN, OUTPUT);
  digitalWrite(MSGEQ7_RESET_PIN, LOW);
  digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
}}

void msgeq7_read() {{
  digitalWrite(MSGEQ7_RESET_PIN, HIGH);
  delayMicroseconds({int(cfg.strobe_delay_us)});
  digitalWrite(MSGEQ7_RESET_PIN, LOW);

  for (int i = 0; i < 7; i++) {{
    digitalWrite(MSGEQ7_STROBE_PIN, LOW);
    delayMicroseconds({int(cfg.strobe_delay_us)});

    int rawL = analogRead(MSGEQ7_LEFT_PIN);
    int rawR = analogRead(MSGEQ7_RIGHT_PIN);

    digitalWrite(MSGEQ7_STROBE_PIN, HIGH);
    delayMicroseconds({int(cfg.strobe_delay_us)});

    rawL -= {int(cfg.noise_floor)};
    rawR -= {int(cfg.noise_floor)};
    if (rawL < 0) rawL = 0;
    if (rawR < 0) rawR = 0;

    float g = {float(cfg.gain)};
    bandL[i] = clamp1023((int)(rawL * g));
    bandR[i] = clamp1023((int)(rawR * g));
    bandM[i] = (uint16_t)((bandL[i] + bandR[i]) / 2);
  }}
}}

void setup() {{
  FastLED.addLeds<NEOPIXEL, LED_PIN>(leds, LED_COUNT);
  FastLED.setBrightness(BRIGHTNESS);
  msgeq7_setup();
}}

void loop() {{
  msgeq7_read();

  // Draw 7 bars across the strip. Each bar uses a segment.
  const int seg = (LED_COUNT / 7);
  for (int i = 0; i < LED_COUNT; i++) {{
    leds[i] = CRGB::Black;
  }}

  for (int b = 0; b < 7; b++) {{
    // bar height in pixels within its segment
    int start = b * seg;
    int end = (b == 6) ? (LED_COUNT - 1) : (start + seg - 1);
    int span = (end - start + 1);

    // map band 0..1023 => 0..span
    int h = (int)((bandM[b] / 1023.0f) * span);
    if (h < 0) h = 0;
    if (h > span) h = span;

    for (int j = 0; j < h; j++) {{
      int idx = start + j;
      if (idx >= 0 && idx < LED_COUNT) {{
        // simple gradient: low->high
        leds[idx] = CHSV((uint8_t)(b * 36), 255, 255);
      }}
    }}
  }}

  FastLED.show();
  delay(16);
}}
"""


def default_demo() -> str:
    return make_demo_sketch(DemoConfig())
