"""Signal Bus (Phase 6.1)

Deterministic, inspectable signal container used by Rules/Triggers.

MVP (Phase 6.1):
  - time signals
  - engine frame counter
  - audio signals (from AudioSim state)

Design constraints:
  - Never crash callers: all APIs are best-effort.
  - Deterministic ordering for inspection.
  - Stable signal names (string keys).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.signal_registry import REGISTRY

from typing import Any, Dict, List, Optional, Tuple


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@dataclass
class SignalSnapshot:
    """Immutable-ish snapshot for UI polling."""

    t: float
    dt: float
    frame: int
    signals: Dict[str, Any]


class SignalBus:
    """A small, deterministic signal container.

    The bus is updated by the engine/UI each tick. Consumers (Rules UI, inspectors)
    pull snapshots. A future Rules engine will evaluate against this bus.
    """

    def __init__(self):
        self._t: float = 0.0
        self._dt: float = 0.0
        self._frame: int = 0
        self._signals: Dict[str, Any] = {}

    def update(
        self,
        *,
        t: float,
        dt: float,
        frame: int,
        audio_state: Optional[Dict[str, float]] = None,
        variables_state: Optional[Dict[str, Any]] = None,
        derived_signals: Optional[Dict[str, Any]] = None,
        time_mode: str = "SIM_FIXED_DT",
        time_paused: bool = False,
        time_tick: int = 0,
        time_fixed_dt: float = 1.0/60.0,
    ) -> None:
        """Update the bus with the latest time/audio values."""
        try:
            self._t = float(t)
        except Exception:
            self._t = 0.0
        try:
            self._dt = float(dt)
        except Exception:
            self._dt = 0.0
        try:
            self._frame = int(frame)
        except Exception:
            self._frame = 0

        sig: Dict[str, Any] = {}
        sig["time.t"] = float(self._t)
        sig["time.dt"] = float(self._dt)
        sig["engine.frame"] = int(self._frame)
        # Canonical aliases (registry compatibility)
        sig["time"] = float(self._t)
        sig["dt"] = float(self._dt)
        sig["frame"] = int(self._frame)

        # TimeSource v1 metadata
        sig["time.mode"] = str(time_mode)
        sig["time.paused"] = bool(time_paused)
        sig["time.tick"] = int(time_tick)
        sig["time.fixed_dt"] = float(time_fixed_dt)


        # Audio signals (0..1). We support the AudioSim state keys:
        # energy, mono0..mono6, l0..l6, r0..r6
        a = audio_state if isinstance(audio_state, dict) else {}
        try:
            sig["audio.energy"] = _clamp01(float(a.get("energy", 0.0)))
        except Exception:
            sig["audio.energy"] = 0.0

        mono: List[float] = [0.0] * 7
        left: List[float] = [0.0] * 7
        right: List[float] = [0.0] * 7
        for i in range(7):
            try:
                mono[i] = _clamp01(float(a.get(f"mono{i}", 0.0)))
            except Exception:
                mono[i] = 0.0
            try:
                left[i] = _clamp01(float(a.get(f"l{i}", 0.0)))
            except Exception:
                left[i] = 0.0
            try:
                right[i] = _clamp01(float(a.get(f"r{i}", 0.0)))
            except Exception:
                right[i] = 0.0

            sig[f"audio.mono{i}"] = mono[i]
            sig[f"audio.L{i}"] = left[i]
            sig[f"audio.R{i}"] = right[i]

        # Also expose vector forms (useful later; UI will stringify).
        sig["audio.mono"] = mono
        sig["audio.left"] = left
        sig["audio.right"] = right


        # Variables (Phase 6.2)
        vstate = variables_state if isinstance(variables_state, dict) else {}
        try:
            nums = vstate.get("number") if isinstance(vstate.get("number"), dict) else {}
            for name in sorted(nums.keys(), key=lambda x: str(x)):
                try:
                    sig[f"vars.number.{name}"] = float(nums.get(name, 0.0))
                except Exception:
                    sig[f"vars.number.{name}"] = 0.0
        except Exception:
            pass
        try:
            tgl = vstate.get("toggle") if isinstance(vstate.get("toggle"), dict) else {}
            for name in sorted(tgl.keys(), key=lambda x: str(x)):
                try:
                    sig[f"vars.toggle.{name}"] = bool(tgl.get(name, False))
                except Exception:
                    sig[f"vars.toggle.{name}"] = False
        except Exception:
            pass

        # Derived/system signals (Phase 6.4)
        d = derived_signals if isinstance(derived_signals, dict) else {}
        try:
            for k in sorted(d.keys(), key=lambda x: str(x)):
                sig[str(k)] = d.get(k)
        except Exception:
            pass

        self._signals = sig

    def snapshot(self) -> SignalSnapshot:
        """Return a copy-safe snapshot."""
        try:
            sig_copy = dict(self._signals)
        except Exception:
            sig_copy = {}
        return SignalSnapshot(t=float(self._t), dt=float(self._dt), frame=int(self._frame), signals=sig_copy)

    def registry_defs(self):
        """Return known signal definitions (contract), if available."""
        try:
            return REGISTRY.all()
        except Exception:
            return []

    def validate_signal_keys(self, keys):
        """Return unknown keys against registry."""
        try:
            return REGISTRY.validate_keys(keys)
        except Exception:
            return []

    def get(self, name: str, default: Any = None) -> Any:
        """Dict-like accessor used by Qt diagnostics panels."""
        try:
            return self._signals.get(str(name), default)
        except Exception:
            return default

    def iter_items(self) -> List[Tuple[str, Any]]:
        """Deterministic list of (name,value) for UI."""
        try:
            items = list(self._signals.items())
        except Exception:
            items = []
        # Sort by key for stability.
        items.sort(key=lambda kv: str(kv[0]))
        return items
