from __future__ import annotations

"""Modulation model (wired)

This defines the canonical JSON representation for layer modulation bindings ("modulotors").

Contract:
- Layer modulation bindings live at layer['modulotors'] as a list[dict].
- Each binding is validated and normalized before runtime/export consumption.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ModulationBinding:
    enabled: bool = True
    source: str = "lfo"           # lfo | energy | mono0..6 | L0..6 | R0..6
    amount: float = 0.25          # 0..1 (clamped)
    target: str = ""              # param key to modulate (e.g. "speed")
    mode: str = "add"             # add | mul (export/runtime may differ)
    rate_hz: float = 0.5          # for lfo source
    phase: float = 0.0            # 0..1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "source": str(self.source),
            "amount": float(self.amount),
            "target": str(self.target),
            "mode": str(self.mode),
            "rate_hz": float(self.rate_hz),
            "phase": float(self.phase),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ModulationBinding":
        if not isinstance(d, dict):
            return ModulationBinding(enabled=False)
        b = ModulationBinding()
        b.enabled = bool(d.get("enabled", True))
        b.source = str(d.get("source", b.source) or b.source)
        try:
            b.amount = float(d.get("amount", b.amount))
        except Exception:
            b.amount = b.amount
        b.target = str(d.get("target", b.target) or "")
        b.mode = str(d.get("mode", b.mode) or b.mode)
        try:
            b.rate_hz = float(d.get("rate_hz", b.rate_hz))
        except Exception:
            b.rate_hz = b.rate_hz
        try:
            b.phase = float(d.get("phase", b.phase))
        except Exception:
            b.phase = b.phase
        return b

    def normalize(self) -> "ModulationBinding":
        # clamp
        if self.amount < 0.0:
            self.amount = 0.0
        if self.amount > 1.0:
            self.amount = 1.0
        if self.phase < 0.0:
            self.phase = 0.0
        if self.phase > 1.0:
            self.phase = 1.0
        if self.rate_hz < 0.0:
            self.rate_hz = 0.0
        if self.rate_hz > 10.0:
            self.rate_hz = 10.0
        self.source = (self.source or "lfo").strip()
        self.mode = (self.mode or "add").strip().lower()
        if self.mode not in ("add", "mul"):
            self.mode = "add"
        self.target = (self.target or "").strip()
        return self
