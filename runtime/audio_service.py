from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

# Reuse existing deterministic simulator for now.
# IMPORTANT: release-plan R1 is about OWNERSHIP/TRUTH, not changing algorithms.
from preview.audio import AudioSim


class AudioService:
    """Engine-owned always-on audio service.

    Contract:
      - `step(t)` advances the backend to simulation time `t` (seconds).
      - `.state` is always a dict with canonical keys after at least one step.
      - Backend is pluggable later (serial/MSGEQ7/etc), but service ownership is stable.

    This deliberately wraps the existing `AudioSim` so we can rewire ownership without
    rewriting effects or preview code.
    """

    def __init__(self, backend: Optional[Any] = None):
        self.backend = backend or AudioSim()
        self._last_t: Optional[float] = None
        # Prime immediately so startup diagnostics can show non-zero values.
        try:
            self.step(0.0)
        except Exception:
            pass

    def step(self, t: float) -> None:
        tt = float(t) if t is not None else 0.0
        # Guard against redundant stepping at the same timestamp.
        if self._last_t is not None and abs(tt - self._last_t) < 1e-9:
            return
        self._last_t = tt
        if hasattr(self.backend, "step"):
            self.backend.step(tt)

    @property
    def state(self):
        return getattr(self.backend, "state", None)

    @property
    def mode(self) -> str:
        return str(getattr(self.backend, "mode", "sim") or "sim")

    @property
    def backend_name(self) -> str:
        return type(self.backend).__name__

    @property
    def status(self) -> str:
        return str(getattr(self.backend, "status", "OK") or "OK")

    @property
    def last_error(self) -> str:
        return str(getattr(self.backend, "last_error", "") or "")


    @property
    def mode(self) -> str:
        return "sim"

    @property
    def backend_name(self) -> str:
        try:
            return type(self.backend).__name__
        except Exception:
            return "unknown"

    @property
    def status(self) -> str:
        return "OK"

    def get_audio_state_dict(self) -> dict:
        """Return backend audio state in canonical AudioSim keys.

        Keys: energy, mono0..mono6, l0..l6, r0..r6
        """
        try:
            st = getattr(self.backend, "state", None)
            return dict(st) if isinstance(st, dict) else {}
        except Exception:
            return {}
