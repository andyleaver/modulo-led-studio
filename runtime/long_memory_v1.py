from __future__ import annotations

"""Long-memory primitives (engine-safe, deterministic).

Goal:
- Provide reusable memory buffers that evolve over minutes/hours (decay + reinforcement)
- Keep math deterministic and export-friendly (no wall-clock, no randomness unless seeded externally)

This module intentionally does NOT implement persistence-to-disk/flash.
Persistence is Phase 2 (Data & Memory Systems).
"""

from dataclasses import dataclass
import math
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class LongMemory2DConfig:
    width: int
    height: int
    half_life_s: float = 30.0  # exponential half-life in seconds
    clamp01: bool = True


class LongMemory2D:
    """A scalar memory buffer over a 2D grid in [0,1], with exponential decay.

    - step(dt) applies decay.
    - reinforce_points() deposits energy at points (optionally with radius falloff).

    Designed to be used by behaviors that run across many frames.
    """

    def __init__(self, cfg: LongMemory2DConfig):
        if cfg.width <= 0 or cfg.height <= 0:
            raise ValueError("LongMemory2D: width/height must be > 0")
        if cfg.half_life_s <= 0:
            raise ValueError("LongMemory2D: half_life_s must be > 0")
        self.cfg = cfg
        self.w = int(cfg.width)
        self.h = int(cfg.height)
        self.buf: List[float] = [0.0] * (self.w * self.h)

    def clear(self):
        for i in range(len(self.buf)):
            self.buf[i] = 0.0

    def _idx(self, x: int, y: int) -> int:
        return (y % self.h) * self.w + (x % self.w)

    def step(self, dt: float):
        """Apply exponential decay."""
        if dt <= 0:
            return
        # decay factor so value halves every half_life_s
        # factor = 2^(-dt/half_life)
        factor = math.exp(-math.log(2.0) * (dt / float(self.cfg.half_life_s)))
        b = self.buf
        for i in range(len(b)):
            b[i] *= factor

    def reinforce_points(
        self,
        points: Iterable[Tuple[float, float]],
        amount: float = 0.25,
        radius: float = 0.0,
        wrap: bool = True,
    ):
        """Deposit `amount` at each point.

        points: (x,y) in grid coordinates (float ok)
        radius: if >0, applies a gaussian-ish falloff within radius.
        """
        if amount == 0:
            return
        r = float(radius)
        if r <= 0.0:
            for (x, y) in points:
                xi = int(round(x))
                yi = int(round(y))
                if wrap:
                    idx = self._idx(xi, yi)
                    self.buf[idx] += amount
                else:
                    if 0 <= xi < self.w and 0 <= yi < self.h:
                        self.buf[yi * self.w + xi] += amount
        else:
            # bounded kernel; keep deterministic and cheap
            rr = r * r
            x0 = -int(math.ceil(r))
            x1 = int(math.ceil(r))
            y0 = -int(math.ceil(r))
            y1 = int(math.ceil(r))
            for (x, y) in points:
                cx = float(x)
                cy = float(y)
                icx = int(round(cx))
                icy = int(round(cy))
                for oy in range(y0, y1 + 1):
                    for ox in range(x0, x1 + 1):
                        dx = (icx + ox) - cx
                        dy = (icy + oy) - cy
                        d2 = dx * dx + dy * dy
                        if d2 > rr:
                            continue
                        # Smooth falloff; not true gaussian but good enough.
                        w = 1.0 - (d2 / rr) if rr > 0 else 1.0
                        dep = amount * max(0.0, w)
                        xi = icx + ox
                        yi = icy + oy
                        if wrap:
                            idx = self._idx(xi, yi)
                            self.buf[idx] += dep
                        else:
                            if 0 <= xi < self.w and 0 <= yi < self.h:
                                self.buf[yi * self.w + xi] += dep

        if self.cfg.clamp01:
            b = self.buf
            for i in range(len(b)):
                if b[i] < 0.0:
                    b[i] = 0.0
                elif b[i] > 1.0:
                    b[i] = 1.0

    def sample(self, x: int, y: int) -> float:
        return self.buf[self._idx(x, y)]

    def as_list(self) -> List[float]:
        return list(self.buf)


@dataclass
class EventRecordV1:
    t: float
    kind: str
    payload: dict


class EventLogV1:
    """A bounded event log for long-running behaviors (preview only).

    Useful for long-memory systems + later Phase 2 persistence.
    """

    def __init__(self, capacity: int = 2048):
        self.capacity = max(1, int(capacity))
        self._events: List[EventRecordV1] = []

    def add(self, t: float, kind: str, payload: Optional[dict] = None):
        self._events.append(EventRecordV1(float(t), str(kind), dict(payload or {})))
        if len(self._events) > self.capacity:
            # drop oldest
            self._events = self._events[-self.capacity :]

    def list(self) -> List[EventRecordV1]:
        return list(self._events)
