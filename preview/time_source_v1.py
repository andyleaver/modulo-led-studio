from __future__ import annotations
"""
TimeSource v1

Single authoritative time contract for preview + rules + deterministic systems.

Modes:
- SIM_FIXED_DT: deterministic fixed-step simulation time driven by incoming wall timestamps.
- SIM_REALTIME: variable-dt simulation time (smoother preview, less export-parity).
- WALLCLOCK: uses wall clock as simulation time (installations / time-based pieces).

This module is engine-level; UI may call pause/step, but it does not depend on UI.
"""
from dataclasses import dataclass
import time as _time
from preview.sim_clock import SimClock

@dataclass
class TimeSnapshot:
    mode: str
    paused: bool
    fixed_dt: float
    t: float        # simulation seconds (relative)
    dt: float       # delta seconds for last update
    tick: int       # simulation tick counter (fixed steps in fixed mode)
    frame: int      # render frame counter
    wall_t: float   # last wall timestamp observed (seconds)

class TimeSourceV1:
    MODES = ("SIM_FIXED_DT", "SIM_REALTIME", "WALLCLOCK")

    def __init__(self, *, mode: str = "SIM_FIXED_DT", fixed_dt: float = 1.0/60.0, seed: int = 1):
        self.mode = mode if mode in self.MODES else "SIM_FIXED_DT"
        self.fixed_dt = float(fixed_dt)
        self.seed = int(seed) if isinstance(seed, int) else 1

        self.paused = False
        self._clock = SimClock(fixed_dt=self.fixed_dt)
        self._wall_last = None
        self._t = 0.0
        self._dt = 0.0
        self._tick = 0
        self._frame = 0
        self._wall_t = 0.0

    def reset(self) -> None:
        self._clock.reset()
        self._wall_last = None
        self._t = 0.0
        self._dt = 0.0
        self._tick = 0
        self._frame = 0
        self._wall_t = 0.0

    def set_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            return
        if mode != self.mode:
            self.mode = mode
            # reset accumulation to avoid discontinuities
            self.reset()

    def set_fixed_dt(self, fixed_dt: float) -> None:
        try:
            fd = float(fixed_dt)
        except Exception:
            return
        if fd <= 0:
            return
        self.fixed_dt = fd
        self._clock.fixed_dt = fd

    def set_paused(self, paused: bool) -> None:
        self.paused = bool(paused)

    def step_wall(self, wall_t: float | None = None) -> TimeSnapshot:
        """Advance time source based on wall timestamp (seconds)."""
        if wall_t is None:
            wall_t = float(_time.time())
        try:
            wall_t = float(wall_t)
        except Exception:
            wall_t = float(_time.time())

        self._frame += 1
        self._wall_t = wall_t

        if self.paused:
            self._dt = 0.0
            return self.snapshot()

        if self.mode == "SIM_FIXED_DT":
            steps = self._clock.step_to(wall_t)
            self._tick += int(steps)
            self._dt = float(self._clock.fixed_dt) if steps > 0 else 0.0
            self._t = float(self._clock.sim_time)
            return self.snapshot()

        if self.mode == "SIM_REALTIME":
            if self._wall_last is None:
                self._wall_last = wall_t
                self._dt = 0.0
                return self.snapshot()
            dt = max(0.0, wall_t - float(self._wall_last))
            if dt > 0.5:
                dt = 0.5
            self._wall_last = wall_t
            self._dt = float(dt)
            self._t += float(dt)
            self._tick += 1
            return self.snapshot()

        # WALLCLOCK
        if self._wall_last is None:
            self._wall_last = wall_t
            self._dt = 0.0
        else:
            dt = max(0.0, wall_t - float(self._wall_last))
            if dt > 0.5:
                dt = 0.5
            self._dt = float(dt)
            self._wall_last = wall_t
        # Use wall_t as absolute time, but also expose relative via t if desired
        self._t = float(wall_t)
        self._tick += 1
        return self.snapshot()

    def step_ticks(self, n: int = 1) -> TimeSnapshot:
        """Force-advance fixed-dt ticks (works even if paused). Intended for stepping."""
        try:
            n = int(n)
        except Exception:
            n = 1
        if n <= 0:
            return self.snapshot()
        # Only meaningful in SIM_FIXED_DT; still advances t in that manner
        for _ in range(n):
            self._tick += 1
            self._t += float(self.fixed_dt)
        self._dt = float(self.fixed_dt)
        self._frame += 1
        return self.snapshot()

    def snapshot(self) -> TimeSnapshot:
        return TimeSnapshot(
            mode=str(self.mode),
            paused=bool(self.paused),
            fixed_dt=float(self.fixed_dt),
            t=float(self._t),
            dt=float(self._dt),
            tick=int(self._tick),
            frame=int(self._frame),
            wall_t=float(self._wall_t),
        )
