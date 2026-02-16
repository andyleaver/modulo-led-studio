"""Modulo modulation helpers.

This module provides a stable import path used by params resolution and the preview engine.
If modulation is not enabled, these definitions remain deterministic no-ops.

No monkey-patching. No runtime import interception.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import math


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _get_seq(x: Any) -> Optional[Sequence[float]]:
    if x is None:
        return None
    # accept list/tuple etc
    if isinstance(x, (list, tuple)):
        return x
    # accept numpy arrays without importing numpy
    if hasattr(x, "__len__") and hasattr(x, "__getitem__"):
        try:
            _ = x[0]
            return x
        except Exception:
            return None
    return None


def apply_mod(base_value: float, mod_signal: float, mode: str, amount: float) -> float:
    """Apply a modulation signal to a base value.

    Modes:
      - add: base + signal * amount
      - set: signal * amount
      - mul (default): base * (1 + signal * amount)
    """
    mode = (mode or "mul").lower().strip()
    amt = float(amount)

    if mode == "add":
        return float(base_value) + float(mod_signal) * amt
    if mode == "set":
        return float(mod_signal) * amt
    return float(base_value) * (1.0 + float(mod_signal) * amt)


@dataclass(frozen=True)
class Modulotor:
    """A modulation source routed to a float parameter.

    This is intentionally minimal. The current runtime treats modulators as optional.
    When modulation is implemented, `kind/key` can represent routed signal sources.
    """
    target: str = ""
    kind: str = "none"
    key: str = "∅"
    mode: str = "mul"
    amount: float = 0.0

    def sample(self, t: float, *, audio: Any = None) -> float:
        """Sample a modulation signal in the normalized range [0..1].

        Supported kinds (minimal deterministic subset):
          - kind='lfo', key='sine' or 'sine:<rate_hz>'
          - kind='audio', key='energy' | 'mono0..6' | 'L0..6' | 'R0..6'

        The preview engine passes in its current audio context; Arduino export may
        later map these to MSGEQ7 band values.
        """

        kind = (self.kind or "").strip().lower()
        key = (self.key or "").strip()

        # ---- LFO ----
        if kind in ("lfo", "osc", "oscillator"):
            # key formats: 'sine' or 'sine:1.25'
            rate_hz = 1.0
            if ":" in key:
                head, tail = key.split(":", 1)
                key_head = head.strip().lower()
                if key_head:
                    key = key_head
                try:
                    rate_hz = float(tail)
                except Exception:
                    rate_hz = 1.0
            else:
                key = key.strip().lower() or "sine"

            if key in ("sine", "sin"):
                # Map [-1..1] -> [0..1]
                v = 0.5 + 0.5 * math.sin(2.0 * math.pi * rate_hz * t)
                return _clamp01(v)

            return 0.0

        # ---- AUDIO ----
        if kind in ("audio", "aud"):
            # Accept both 'mono0' and 'mono:0'
            k = key.replace(" ", "")
            if ":" in k:
                a, b = k.split(":", 1)
                k = f"{a}{b}"
            k = k.lower()

            # audio may be a dict-like or object-like.
            if audio is None:
                return 0.0

            # energy
            if k in ("energy", "rms", "level"):
                v = None
                if isinstance(audio, dict):
                    v = audio.get("energy")
                else:
                    v = _get_attr(audio, "energy", None)
                try:
                    return _clamp01(float(v))
                except Exception:
                    return 0.0

            # bands: mono0..6, l0..6, r0..6
            def _band(arr_name: str, idx: int) -> float:
                arr = None
                if isinstance(audio, dict):
                    arr = audio.get(arr_name)
                else:
                    arr = _get_attr(audio, arr_name, None)
                arr = _get_seq(arr)
                if not arr:
                    return 0.0
                if idx < 0 or idx >= len(arr):
                    return 0.0
                try:
                    return _clamp01(float(arr[idx]))
                except Exception:
                    return 0.0

            for prefix, arr_name in (("mono", "mono"), ("l", "L"), ("r", "R")):
                if k.startswith(prefix):
                    try:
                        idx = int(k[len(prefix):])
                    except Exception:
                        idx = 0
                    return _band(arr_name, idx)

            return 0.0

        return 0.0


def sample(mod: Optional[Modulotor], t: float, ctx: Any = None) -> float:
    """Legacy helper used by older call sites."""
    if mod is None:
        return 0.0
    try:
        return float(mod.sample(float(t), audio=ctx))
    except Exception:
        return 0.0
