from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, Any

def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x

EVENT_UNIPOLAR = {
    'audio_beat','audio_kick','audio_snare','audio_onset','audio_sec_change',
    'audio_bpm','audio_bpm_conf','audio_sec_id',
    'audio_tr_L0','audio_tr_L1','audio_tr_L2','audio_tr_L3','audio_tr_L4','audio_tr_L5','audio_tr_L6',
    'audio_tr_R0','audio_tr_R1','audio_tr_R2','audio_tr_R3','audio_tr_R4','audio_tr_R5','audio_tr_R6',
    'audio_pk_L0','audio_pk_L1','audio_pk_L2','audio_pk_L3','audio_pk_L4','audio_pk_L5','audio_pk_L6',
    'audio_pk_R0','audio_pk_R1','audio_pk_R2','audio_pk_R3','audio_pk_R4','audio_pk_R5','audio_pk_R6',
}

def _audio_bipolar(v01: float) -> float:
    # map 0..1 -> -1..1
    return (_clamp01(float(v01)) - 0.5) * 2.0

@dataclass
class Modulotor:
    source: str = "none"     # see params.registry.SOURCES
    target: str = "brightness"
    mode: str = "mul"        # 'add' | 'mul' | 'set'
    amount: float = 0.5
    rate_hz: float = 0.5     # for LFO sources
    bias: float = 0.0

    # one-pole smoothing in signal space (0=no smoothing, closer to 1=more smoothing)
    smooth: float = 0.0
    _last: Optional[float] = None

def sample(self, t: float, audio: Any = None) -> float:
    src = (self.source or "none").strip()

    if src == "none":
        sig = 0.0
    elif src == "lfo_sine":
        sig = math.sin(2.0 * math.pi * float(self.rate_hz) * float(t))  # [-1..1]
    elif src.startswith("audio_"):
        if audio is None:
            sig = 0.0
        else:
            try:
                if src in EVENT_UNIPOLAR:
                    try:
                        sig = _clamp01(float(audio.get(src, 0.0)))
                    except Exception:
                        sig = 0.0
                elif src == "audio_energy":
                    sig = _audio_bipolar(audio.get("energy", 0.0))
                elif src.startswith("audio_mono"):
                    i = int(src.replace("audio_mono", ""))
                    sig = _audio_bipolar((audio.get("mono") or [0.0]*7)[i])
                elif src.startswith("audio_L"):
                    i = int(src.replace("audio_L", ""))
                    sig = _audio_bipolar((audio.get("left") or [0.0]*7)[i])
                elif src.startswith("audio_R"):
                    i = int(src.replace("audio_R", ""))
                    sig = _audio_bipolar((audio.get("right") or [0.0]*7)[i])
                else:
                    sig = 0.0
            except Exception:
                sig = 0.0
    elif src.startswith("purpose_"):
        if audio is None:
            sig = 0.0
        else:
            try:
                v01 = float(audio.get(src, 0.0))
                sig = _audio_bipolar(v01)
            except Exception:
                sig = 0.0
    else:
        sig = 0.0

    sig = sig + float(self.bias)

    if self.smooth and self.smooth > 0.0:
        a = max(0.0, min(0.999, float(self.smooth)))
        if self._last is None:
            self._last = sig
        else:
            self._last = a * self._last + (1.0 - a) * sig
        sig = self._last

    return float(sig)



def apply_mod(base_value: float, mod_signal: float, mode: str, amount: float) -> float:
    mode = (mode or "mul").lower().strip()
    amt = float(amount)

    if mode == "add":
        return float(base_value) + float(mod_signal) * amt
    if mode == "set":
        return float(mod_signal) * amt
    # default mul: treat signal as bipolar multiplier around 1.0
    return float(base_value) * (1.0 + float(mod_signal) * amt)
