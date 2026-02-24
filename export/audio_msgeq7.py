"""MSGEQ7 / Spectrum Shield audio backend scaffold for Arduino export (Phase C.4)

This module is **codegen-only**: it emits Arduino C++ snippets to read MSGEQ7.
It is intentionally not fully wired into the multi-layer exporter yet.

Hardware notes:
- Spectrum Shield uses two MSGEQ7 chips (stereo), 7 bands each.
- Typical wiring (examples, configurable):
  - strobe: D4
  - reset:  D5
  - left:   A0
  - right:  A1

Output contract (planned):
- bandsL[7], bandsR[7], bandsM[7]
- energy, peak (derived)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MSGEQ7Pins:
    strobe: int = 4
    reset: int = 5
    left_adc: str = "A0"
    right_adc: str = "A1"


@dataclass(frozen=True)
class MSGEQ7Config:
    pins: MSGEQ7Pins = MSGEQ7Pins()
    noise_floor: int = 60
    gain: float = 1.0
    # sample delay microseconds between strobe toggles (typical 30-50us)
    strobe_delay_us: int = 30


def emit_msgeq7_declarations(cfg: MSGEQ7Config) -> str:
    p = cfg.pins
    return f"""    // --- MSGEQ7 (stereo) declarations ---
const int PIN_STROBE = {p.strobe};
const int PIN_RESET  = {p.reset};
const int PIN_LEFT   = {p.left_adc};
const int PIN_RIGHT  = {p.right_adc};

uint16_t audioL[7];
uint16_t audioR[7];
uint16_t audioM[7];
uint16_t audioEnergy = 0;
uint16_t audioPeak   = 0;
"""


def emit_msgeq7_setup(cfg: MSGEQ7Config) -> str:
    return f"""    // --- MSGEQ7 setup ---
pinMode(PIN_STROBE, OUTPUT);
pinMode(PIN_RESET, OUTPUT);
digitalWrite(PIN_STROBE, HIGH);
digitalWrite(PIN_RESET, LOW);
"""


def emit_msgeq7_read_function(cfg: MSGEQ7Config) -> str:
    # Keep code simple and deterministic; use integer math where possible.
    nf = int(cfg.noise_floor)
    delay_us = int(cfg.strobe_delay_us)
    gain = float(cfg.gain)

    # We emit gain as float multiplier but clamp to uint16.
    return f"""    // --- MSGEQ7 read (stereo) ---
void readMSGEQ7() {{
  digitalWrite(PIN_RESET, HIGH);
  delayMicroseconds({delay_us});
  digitalWrite(PIN_RESET, LOW);

  uint16_t peak = 0;
  uint32_t energy = 0;

  for (int i = 0; i < 7; i++) {{
    digitalWrite(PIN_STROBE, LOW);
    delayMicroseconds({delay_us});

    int rawL = analogRead(PIN_LEFT);
    int rawR = analogRead(PIN_RIGHT);

    digitalWrite(PIN_STROBE, HIGH);
    delayMicroseconds({delay_us});

    // noise floor
    rawL = rawL - {nf};
    rawR = rawR - {nf};
    if (rawL < 0) rawL = 0;
    if (rawR < 0) rawR = 0;

    // gain
    float g = {gain};
    uint16_t vL = (uint16_t)min(1023.0f, rawL * g);
    uint16_t vR = (uint16_t)min(1023.0f, rawR * g);
    uint16_t vM = (uint16_t)((vL + vR) / 2);

    audioL[i] = vL;
    audioR[i] = vR;
    audioM[i] = vM;

    energy += (uint32_t)vM;
    if (vM > peak) peak = vM;
  }}

  audioEnergy = (uint16_t)min((uint32_t)65535, energy);
  audioPeak = peak;
}}
"""


def emit_msgeq7_all(cfg: MSGEQ7Config) -> str:
    return "\n".join([
        emit_msgeq7_declarations(cfg).rstrip(),
        "",
        emit_msgeq7_setup(cfg).rstrip(),
        "",
        emit_msgeq7_read_function(cfg).rstrip(),
        ""
    ]) + "\n"
