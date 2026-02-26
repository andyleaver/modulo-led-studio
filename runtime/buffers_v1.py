from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import math

@dataclass
class BufferConfig:
    width: int
    height: int
    clamp_min: float = 0.0
    clamp_max: float = 1.0

class ScalarBufferV1:
    """A simple scalar grid buffer (layout-space), designed for trails/heatmaps/pheromones.

    This is an engine primitive (not an effect). It is deterministic and JSON-serializable.
    """

    def __init__(self, cfg: BufferConfig):
        self.cfg = cfg
        self.w = int(cfg.width)
        self.h = int(cfg.height)
        self.data: List[float] = [0.0] * (self.w * self.h)

    def _idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def clear(self, v: float = 0.0) -> None:
        self.data[:] = [float(v)] * (self.w * self.h)

    def get(self, x: int, y: int) -> float:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return 0.0
        return self.data[self._idx(x, y)]

def sample_bilinear(self, x: float, y: float) -> float:
    """
    Bilinear sample in buffer grid coordinates.
    Out-of-bounds returns 0.0.
    """
    fx = float(x)
    fy = float(y)
    x0 = int(math.floor(fx))
    y0 = int(math.floor(fy))
    x1 = x0 + 1
    y1 = y0 + 1

    sx = fx - x0
    sy = fy - y0

    v00 = self.get(x0, y0)
    v10 = self.get(x1, y0)
    v01 = self.get(x0, y1)
    v11 = self.get(x1, y1)

    vx0 = v00 * (1.0 - sx) + v10 * sx
    vx1 = v01 * (1.0 - sx) + v11 * sx
    return vx0 * (1.0 - sy) + vx1 * sy
    def set(self, x: int, y: int, v: float) -> None:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        self.data[self._idx(x, y)] = float(v)

    def add(self, x: int, y: int, v: float) -> None:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._idx(x, y)
        self.data[i] = float(self.data[i] + v)

    def add_splat(self, fx: float, fy: float, v: float, radius: float = 1.5) -> None:
        """Add to nearby cells with a soft radial falloff."""
        if radius <= 0:
            self.add(int(round(fx)), int(round(fy)), v)
            return
        cx = int(math.floor(fx))
        cy = int(math.floor(fy))
        r = int(math.ceil(radius))
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                dx = (xx + 0.5) - fx
                dy = (yy + 0.5) - fy
                d = math.sqrt(dx * dx + dy * dy)
                if d > radius:
                    continue
                w = 1.0 - (d / radius)
                self.add(xx, yy, v * w)

    def clamp(self) -> None:
        mn = self.cfg.clamp_min
        mx = self.cfg.clamp_max
        self.data[:] = [mn if v < mn else mx if v > mx else v for v in self.data]

    def decay(self, factor: float) -> None:
        """Multiply all cells by factor (0..1)."""
        f = float(factor)
        self.data[:] = [v * f for v in self.data]

    def blur_box(self, radius: int = 1, passes: int = 1) -> None:
        """Fast-ish box blur. radius=1 gives a 3x3 average."""
        r = max(0, int(radius))
        p = max(1, int(passes))
        if r == 0:
            return
        for _ in range(p):
            src = self.data
            dst = [0.0] * (self.w * self.h)
            for y in range(self.h):
                for x in range(self.w):
                    s = 0.0
                    c = 0
                    for yy in range(y - r, y + r + 1):
                        if yy < 0 or yy >= self.h:
                            continue
                        row = yy * self.w
                        for xx in range(x - r, x + r + 1):
                            if xx < 0 or xx >= self.w:
                                continue
                            s += src[row + xx]
                            c += 1
                    dst[y * self.w + x] = (s / c) if c else 0.0
            self.data = dst

    def diffuse(self, rate: float = 0.25) -> None:
        """One-step diffusion to 4-neighbours (stable, cheap)."""
        r = float(rate)
        if r <= 0:
            return
        src = self.data
        dst = src[:]  # start as copy
        for y in range(self.h):
            for x in range(self.w):
                i = y * self.w + x
                v = src[i]
                share = v * r
                remain = v - share
                out = 0.0
                # distribute equally to valid neighbours
                n = 0
                if x > 0: n += 1
                if x < self.w - 1: n += 1
                if y > 0: n += 1
                if y < self.h - 1: n += 1
                if n == 0:
                    continue
                per = share / n
                dst[i] = remain
                if x > 0: dst[i - 1] += per
                if x < self.w - 1: dst[i + 1] += per
                if y > 0: dst[i - self.w] += per
                if y < self.h - 1: dst[i + self.w] += per
        self.data = dst

    def to_dict(self) -> Dict[str, Any]:
        return {
            "w": self.w,
            "h": self.h,
            "cfg": {
                "clamp_min": self.cfg.clamp_min,
                "clamp_max": self.cfg.clamp_max,
            },
            "data": self.data,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ScalarBufferV1":
        w = int(d.get("w", 0))
        h = int(d.get("h", 0))
        cfgd = d.get("cfg", {}) or {}
        buf = ScalarBufferV1(BufferConfig(width=w, height=h,
                                          clamp_min=float(cfgd.get("clamp_min", 0.0)),
                                          clamp_max=float(cfgd.get("clamp_max", 1.0))))
        data = d.get("data", [])
        if isinstance(data, list) and len(data) == w * h:
            buf.data = [float(v) for v in data]
        return buf

class VectorBufferV1:
    """A simple vector grid buffer (vx,vy per cell). Useful for flow maps."""

    def __init__(self, cfg: BufferConfig):
        self.cfg = cfg
        self.w = int(cfg.width)
        self.h = int(cfg.height)
        self.vx: List[float] = [0.0] * (self.w * self.h)
        self.vy: List[float] = [0.0] * (self.w * self.h)

    def _idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def clear(self) -> None:
        self.vx[:] = [0.0] * (self.w * self.h)
        self.vy[:] = [0.0] * (self.w * self.h)

    def add(self, x: int, y: int, vx: float, vy: float) -> None:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._idx(x, y)
        self.vx[i] += float(vx)
        self.vy[i] += float(vy)

    def get(self, x: int, y: int) -> Tuple[float, float]:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return (0.0, 0.0)
        i = self._idx(x, y)
        return (self.vx[i], self.vy[i])

    def decay(self, factor: float) -> None:
        f = float(factor)
        self.vx[:] = [v * f for v in self.vx]
        self.vy[:] = [v * f for v in self.vy]

    def to_dict(self) -> Dict[str, Any]:
        return {"w": self.w, "h": self.h, "vx": self.vx, "vy": self.vy,
                "cfg": {"clamp_min": self.cfg.clamp_min, "clamp_max": self.cfg.clamp_max}}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VectorBufferV1":
        w = int(d.get("w", 0))
        h = int(d.get("h", 0))
        cfgd = d.get("cfg", {}) or {}
        buf = VectorBufferV1(BufferConfig(width=w, height=h,
                                          clamp_min=float(cfgd.get("clamp_min", 0.0)),
                                          clamp_max=float(cfgd.get("clamp_max", 1.0))))
        vx = d.get("vx", [])
        vy = d.get("vy", [])
        if isinstance(vx, list) and isinstance(vy, list) and len(vx) == w * h and len(vy) == w * h:
            buf.vx = [float(v) for v in vx]
            buf.vy = [float(v) for v in vy]
        return buf
