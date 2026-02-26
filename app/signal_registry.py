from __future__ import annotations

"""Signal Registry

Canonical catalog of signal keys used by Rules, modulotors, and diagnostics.

Design goals:
- Deterministic: stable keys and stable ordering.
- Tolerant: runtime SignalBus may publish a superset; registry defines the contract.
- Export truth: each signal can be marked export-available (capability-driven).

This file was previously scaffold-only; it is now wired.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SignalDef:
    key: str
    label: str
    deterministic: bool = True
    available_in_preview: bool = True
    available_in_export: bool = False  # conservative default
    notes: str = ""


class SignalRegistry:
    def __init__(self) -> None:
        self._defs: Dict[str, SignalDef] = {}

    def register(self, s: SignalDef) -> None:
        if not s.key or not isinstance(s.key, str):
            raise ValueError("SignalDef.key must be a non-empty string")
        if s.key in self._defs:
            # Duplicate registration is a programmer error; keep loud for dev.
            raise ValueError(f"Duplicate signal key: {s.key}")
        self._defs[s.key] = s

    def get(self, key: str) -> Optional[SignalDef]:
        return self._defs.get(key)

    def keys(self) -> List[str]:
        return sorted(self._defs.keys())

    def all(self) -> List[SignalDef]:
        return [self._defs[k] for k in self.keys()]

    def validate_keys(self, keys: Iterable[str]) -> List[str]:
        unknown: List[str] = []
        for k in keys:
            if not k:
                continue
            if k not in self._defs:
                unknown.append(str(k))
        return sorted(set(unknown))


# Global registry instance (wired)
REGISTRY = SignalRegistry()

def _register_builtin_signals() -> None:
    # Core time/frame
    REGISTRY.register(SignalDef("time", "Time (seconds)", available_in_export=True))
    REGISTRY.register(SignalDef("dt", "Delta time (seconds)", available_in_export=True))
    REGISTRY.register(SignalDef("frame", "Frame counter", available_in_export=True))

    # TimeSource v1 metadata
    REGISTRY.register(SignalDef("time.mode", "Time source mode", available_in_export=False, notes="SIM_FIXED_DT / SIM_REALTIME / WALLCLOCK"))
    REGISTRY.register(SignalDef("time.paused", "Time paused flag", available_in_export=False))
    REGISTRY.register(SignalDef("time.tick", "Simulation tick counter", available_in_export=True))
    REGISTRY.register(SignalDef("time.fixed_dt", "Fixed dt (seconds)", available_in_export=True))


    # Audio frame contract (engine truth)
    REGISTRY.register(SignalDef("audio.energy", "Audio energy (0..1)", available_in_export=True))
    REGISTRY.register(SignalDef("audio.mono", "Audio mono (0..1)", available_in_export=True))
    for i in range(7):
        REGISTRY.register(SignalDef(f"audio.band.{i}", f"Audio band {i} (mono)", available_in_export=True))
        REGISTRY.register(SignalDef(f"audio.L.{i}", f"Audio band {i} (left)", available_in_export=True))
        REGISTRY.register(SignalDef(f"audio.R.{i}", f"Audio band {i} (right)", available_in_export=True))


    # Derived engine metrics (Phase 6.4)
    REGISTRY.register(SignalDef("signal.entropy", "Frame entropy (0..1)", available_in_export=False, notes="Derived from frame-to-frame pixel deltas"))
    REGISTRY.register(SignalDef("signal.activity", "Smoothed activity (0..1)", available_in_export=False, notes="EMA of entropy"))
    REGISTRY.register(SignalDef("signal.occupancy", "Pixel occupancy (0..1)", available_in_export=False, notes="Fraction of pixels above brightness threshold"))
    REGISTRY.register(SignalDef("signal.motion", "Motion estimate (0..1)", available_in_export=False, notes="Agent/system motion when available; falls back to activity"))
    # Optional purpose channels (preview-only unless exported explicitly)
    for i in range(8):
        REGISTRY.register(SignalDef(f"purpose.{i}", f"Purpose channel {i}", available_in_export=False))

try:
    _register_builtin_signals()
except Exception:
    # Best-effort; never crash importers.
    pass
