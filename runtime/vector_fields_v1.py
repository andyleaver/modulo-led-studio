"""Vector Fields v1 (engine primitive).

A VectorField is a reusable simulation building-block. It is *not* an "effect".
It can drive particles, agents, sprites, tile entities, etc.

Fields are deterministic given their config + the project's seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .noise_v2 import CurlNoise2D, CurlNoiseConfig


class VectorField:
    """Base field interface."""

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        raise NotImplementedError


@dataclass
class ConstantFieldConfig:
    vx: float = 0.0
    vy: float = 0.0


class ConstantField(VectorField):
    def __init__(self, cfg: ConstantFieldConfig | None = None):
        self.cfg = cfg or ConstantFieldConfig()

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        return self.cfg.vx, self.cfg.vy


@dataclass
class RadialFieldConfig:
    cx: float = 0.0
    cy: float = 0.0
    strength: float = 1.0
    falloff: float = 1.0  # 1 => 1/r, 2 => 1/r^2
    mode: str = "attract"  # attract|repel


class RadialField(VectorField):
    def __init__(self, cfg: RadialFieldConfig | None = None):
        self.cfg = cfg or RadialFieldConfig()

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        dx = self.cfg.cx - x
        dy = self.cfg.cy - y
        if self.cfg.mode == "repel":
            dx = -dx
            dy = -dy
        r2 = dx * dx + dy * dy
        if r2 < 1e-6:
            return 0.0, 0.0
        r = math.sqrt(r2)
        inv = 1.0 / (r ** max(0.1, self.cfg.falloff))
        return dx * inv * self.cfg.strength, dy * inv * self.cfg.strength


@dataclass
class VortexFieldConfig:
    cx: float = 0.0
    cy: float = 0.0
    strength: float = 1.0
    falloff: float = 1.0
    clockwise: bool = True


class VortexField(VectorField):
    def __init__(self, cfg: VortexFieldConfig | None = None):
        self.cfg = cfg or VortexFieldConfig()

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        dx = x - self.cfg.cx
        dy = y - self.cfg.cy
        r2 = dx * dx + dy * dy
        if r2 < 1e-6:
            return 0.0, 0.0
        r = math.sqrt(r2)
        inv = 1.0 / (r ** max(0.1, self.cfg.falloff))
        # perpendicular
        if self.cfg.clockwise:
            vx, vy = dy, -dx
        else:
            vx, vy = -dy, dx
        return vx * inv * self.cfg.strength, vy * inv * self.cfg.strength


@dataclass
class CurlNoiseFieldConfig:
    seed: int = 1337
    scale: float = 0.05
    eps: float = 1.0
    strength: float = 1.0
    time_scale: float = 0.0  # if >0, animates by offsetting input with t


class CurlNoiseField(VectorField):
    def __init__(self, cfg: CurlNoiseFieldConfig | None = None):
        self.cfg = cfg or CurlNoiseFieldConfig()
        self._curl = CurlNoise2D(
            CurlNoiseConfig(
                seed=self.cfg.seed,
                scale=self.cfg.scale,
                eps=self.cfg.eps,
                strength=self.cfg.strength,
            )
        )

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        if self.cfg.time_scale and self.cfg.time_scale != 0.0:
            tt = t * self.cfg.time_scale
            return self._curl.curl(x + tt, y - tt)
        return self._curl.curl(x, y)
