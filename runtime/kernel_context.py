from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable

RGB = Tuple[int,int,int]
Coord = Tuple[float,float]

class KernelRNG:
    """Deterministic xorshift32 RNG (stable + fast)."""
    def __init__(self, seed: int):
        self._seed = int(seed) & 0xFFFFFFFF
        self._state = self._seed or 0xA5A5A5A5

    def _next_u32(self) -> int:
        x = self._state & 0xFFFFFFFF
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5)  & 0xFFFFFFFF
        self._state = x & 0xFFFFFFFF
        return self._state

    def random(self) -> float:
        return self._next_u32() / 4294967296.0

    def randint(self, a: int, b: int) -> int:
        if b < a:
            a, b = b, a
        span = (b - a) + 1
        return a + (self._next_u32() % span)

@dataclass
class KernelContext:
    # frame / time
    t: float = 0.0
    dt: float = 0.0
    frame: int = 0

    # pixel (set per pixel call)
    i: int = 0
    x: float = 0.0
    y: float = 0.0

    # config/state
    params: Dict[str, Any] = field(default_factory=dict)
    vars: Dict[str, Any] = field(default_factory=dict)
    seed: int = 1337
    deterministic: bool = True
    rng: KernelRNG = field(default_factory=lambda: KernelRNG(1337))

    # signals
    audio: Optional[Dict[str, Any]] = None
    clock: Optional[Dict[str, Any]] = None

    # surface
    num_leds: int = 0
    coords: Optional[List[Coord]] = None
    surface: Optional[Dict[str, Any]] = None

    # optional helpers
    sample_rgb: Optional[Callable[[float,float], RGB]] = None
    neighbors: Optional[Callable[[int,int], List[int]]] = None
