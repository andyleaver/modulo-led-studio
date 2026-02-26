"""Deterministic noise helpers v2 (engine primitive).

v2 consolidates noise functionality into a single, stable API used by fields/particles/agents.
- No external dependencies
- Deterministic given the same seed and inputs
- Small, fast, and portable to embedded targets if needed

This is *not* an effect: it is a reusable math primitive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _hash_u32(x: int) -> int:
    # xorshift32
    x &= 0xFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17) & 0xFFFFFFFF
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def _mix_u32(a: int, b: int) -> int:
    return _hash_u32(a ^ (_hash_u32(b) + 0x9E3779B9 + ((a << 6) & 0xFFFFFFFF) + (a >> 2)))


def _u32_to_unit(u: int) -> float:
    # map to [0,1)
    return (u & 0xFFFFFFFF) / 4294967296.0


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass(frozen=True)
class Noise2DConfig:
    seed: int = 1337
    # For fBm:
    octaves: int = 4
    lacunarity: float = 2.0
    gain: float = 0.5


class Noise2D:
    """Seeded deterministic 2D value-noise + helpers."""

    def __init__(self, cfg: Noise2DConfig | None = None):
        self.cfg = cfg or Noise2DConfig()

    def _cell_rand(self, ix: int, iy: int) -> float:
        h = _mix_u32(_mix_u32(self.cfg.seed & 0xFFFFFFFF, ix & 0xFFFFFFFF), iy & 0xFFFFFFFF)
        return _u32_to_unit(h)

    def value(self, x: float, y: float) -> float:
        """Smooth value noise in [0,1)."""
        x0 = math.floor(x)
        y0 = math.floor(y)
        xf = x - x0
        yf = y - y0
        u = _smoothstep(xf)
        v = _smoothstep(yf)

        r00 = self._cell_rand(int(x0), int(y0))
        r10 = self._cell_rand(int(x0) + 1, int(y0))
        r01 = self._cell_rand(int(x0), int(y0) + 1)
        r11 = self._cell_rand(int(x0) + 1, int(y0) + 1)

        a = _lerp(r00, r10, u)
        b = _lerp(r01, r11, u)
        return _lerp(a, b, v)

    def signed(self, x: float, y: float) -> float:
        """Signed noise in [-1,1)."""
        return self.value(x, y) * 2.0 - 1.0

    def fbm(self, x: float, y: float, octaves: int | None = None, lacunarity: float | None = None, gain: float | None = None) -> float:
        """Fractal brownian motion (signed, approx [-1,1])."""
        o = octaves if octaves is not None else self.cfg.octaves
        lac = lacunarity if lacunarity is not None else self.cfg.lacunarity
        g = gain if gain is not None else self.cfg.gain

        amp = 1.0
        freq = 1.0
        acc = 0.0
        norm = 0.0
        for _ in range(max(1, int(o))):
            acc += amp * self.signed(x * freq, y * freq)
            norm += amp
            amp *= g
            freq *= lac
        if norm > 0:
            acc /= norm
        return acc

    def grad(self, x: float, y: float, eps: float = 1e-3) -> tuple[float, float]:
        """Numerical gradient of signed noise."""
        nx1 = self.signed(x + eps, y)
        nx0 = self.signed(x - eps, y)
        ny1 = self.signed(x, y + eps)
        ny0 = self.signed(x, y - eps)
        return ((nx1 - nx0) / (2.0 * eps), (ny1 - ny0) / (2.0 * eps))


@dataclass(frozen=True)
class CurlNoiseConfig:
    seed: int = 1337
    scale: float = 0.08
    strength: float = 1.0
    eps: float = 1e-3
    octaves: int = 4
    lacunarity: float = 2.0
    gain: float = 0.5


class CurlNoise2D:
    """Divergence-free 2D flow from the curl of a scalar potential."""

    def __init__(self, cfg: CurlNoiseConfig | None = None):
        self.cfg = cfg or CurlNoiseConfig()
        self._noise = Noise2D(Noise2DConfig(
            seed=self.cfg.seed,
            octaves=self.cfg.octaves,
            lacunarity=self.cfg.lacunarity,
            gain=self.cfg.gain,
        ))

    def sample(self, x: float, y: float, t: float = 0.0) -> tuple[float, float]:
        # Use fbm potential, optionally time-shifted
        s = self.cfg.scale
        eps = self.cfg.eps
        # Potential field:
        def pot(px: float, py: float) -> float:
            return self._noise.fbm(px, py)

        px = (x + t * 0.15) * s
        py = (y + t * 0.11) * s

        dpsi_dx = (pot(px + eps, py) - pot(px - eps, py)) / (2.0 * eps)
        dpsi_dy = (pot(px, py + eps) - pot(px, py - eps)) / (2.0 * eps)

        # curl(psi) in 2D => ( dpsi/dy, -dpsi/dx )
        vx = dpsi_dy * self.cfg.strength
        vy = -dpsi_dx * self.cfg.strength
        return (vx, vy)
