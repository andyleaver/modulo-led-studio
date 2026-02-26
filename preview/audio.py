from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

@dataclass
class AudioFrame:
    energy: float
    mono: List[float]   # 7
    left: List[float]   # 7
    right: List[float]  # 7

    def as_dict(self) -> Dict[str, float]:
        d: Dict[str, float] = {"energy": float(self.energy)}
        for i in range(7):
            d[f"mono{i}"] = float(self.mono[i])
            d[f"l{i}"] = float(self.left[i])
            d[f"r{i}"] = float(self.right[i])
        return d

class AudioSim:
    """Deterministic simulated audio providing Spectrum-style sources.

    Exposes (0..1): energy, mono0..mono6, l0..l6, r0..r6
    """
    def __init__(self):
        # These fields are consumed by Qt diagnostics.
        self.mode = 'sim'
        self.backend = 'AudioSim'
        self.status = 'OK'
        self.last_error = ''
        self.state: Dict[str, float] = {}
        self._update_state(self.frame(0.0))

    def available_sources(self):
        return sorted(list(self.state.keys())) if self.state else ["energy"]

    def frame(self, t: float) -> AudioFrame:
        mono: List[float] = []
        left: List[float] = []
        right: List[float] = []
        base = 0.5 + 0.5 * math.sin(2*math.pi*0.33*t)
        for i in range(7):
            f = 0.20 + i*0.11
            v = 0.5 + 0.5 * math.sin(2*math.pi*f*t + i*0.6)
            v = 0.65*v + 0.35*base
            mono.append(_clamp01(v))
            left.append(_clamp01(0.92*v + 0.08*(0.5+0.5*math.sin(2*math.pi*(f*1.03)*t))))
            right.append(_clamp01(0.92*v + 0.08*(0.5+0.5*math.sin(2*math.pi*(f*0.97)*t + 0.2))))
        energy = _clamp01(sum(mono)/7.0)
        return AudioFrame(energy=energy, mono=mono, left=left, right=right)

    def step(self, t: float):
        self._update_state(self.frame(float(t)))

    def _update_state(self, fr: AudioFrame):
        d = fr.as_dict()
        # Canonical list views expected by diagnostics + several effects.
        d["mono"] = [float(x) for x in fr.mono]
        d["L"] = [float(x) for x in fr.left]
        d["R"] = [float(x) for x in fr.right]
        self.state = d
