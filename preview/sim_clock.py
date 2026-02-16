from __future__ import annotations
"""Fixed-tick simulation clock.

Given incoming render timestamps t (seconds), advances an internal sim_time in fixed dt steps.
This makes stateful/game effects deterministic and export-parity friendly.
"""

class SimClock:
    def __init__(self, fixed_dt: float = 1.0/60.0):
        self.fixed_dt = float(fixed_dt)
        self.sim_time = 0.0
        self._last_t = None
        self._accum = 0.0

    def reset(self):
        self.sim_time = 0.0
        self._last_t = None
        self._accum = 0.0

    def step_to(self, t: float) -> int:
        """Advance clock toward timestamp t. Returns number of fixed steps executed."""
        t = float(t)
        if self._last_t is None:
            self._last_t = t
            return 0
        # If time goes backwards, reset to keep determinism
        if t < self._last_t:
            self.reset()
            self._last_t = t
            return 0
        dt_real = t - self._last_t
        self._last_t = t
        if dt_real > 0.5:
            # clamp huge jumps to avoid spiral; still deterministic
            dt_real = 0.5
        self._accum += dt_real
        steps = 0
        while self._accum >= self.fixed_dt:
            self._accum -= self.fixed_dt
            self.sim_time += self.fixed_dt
            steps += 1
        return steps
