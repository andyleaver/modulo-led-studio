from __future__ import annotations

"""
Particle System v1 (engine primitive)

This is NOT an "effect". It is a reusable simulation primitive that other behaviors
(effects, agents, narratives, rule-driven systems) can configure and render.

Design goals:
- Deterministic when given deterministic dt + seed (TimeSource v1 + project seed)
- Minimal allocations in steady-state
- JSON-serializable state (for World IO / snapshots / replay)
- Layout-agnostic: operates in "layout space" (x,y floats). Renderers decide mapping.
"""

from .integrators_v1 import IntegratorConfigV1, euler_step_entities
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional, Tuple, Any
import math

from behaviors.state_runtime import DeterministicRNG, clamp, wrap

Vec2 = Tuple[float, float]
RGB = Tuple[int, int, int]


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    seed: int = 0
    r: int = 255
    g: int = 255
    b: int = 255

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Particle":
        return Particle(**d)


class Emitter:
    """Base class for emitters. Override emit_one()."""
    def emit(self, system: "ParticleSystemV1", count: int = 1) -> int:
        spawned = 0
        for _ in range(max(0, int(count))):
            p = self.emit_one(system)
            if p is not None:
                system.particles.append(p)
                spawned += 1
        return spawned

    def emit_one(self, system: "ParticleSystemV1") -> Optional[Particle]:
        raise NotImplementedError


class PointEmitter(Emitter):
    def __init__(self, x: float, y: float, speed: float = 0.0, spread: float = math.tau,
                 life: float = 2.0, color: RGB = (255, 255, 255)):
        self.x, self.y = float(x), float(y)
        self.speed = float(speed)
        self.spread = float(spread)
        self.life = float(life)
        self.color = color

    def emit_one(self, system: "ParticleSystemV1") -> Optional[Particle]:
        ang = system.rng.uniform(0.0, self.spread)
        spd = self.speed
        vx = math.cos(ang) * spd
        vy = math.sin(ang) * spd
        seed = system.rng.randint(0, 2**31 - 1)
        r, g, b = self.color
        return Particle(self.x, self.y, vx, vy, self.life, seed, r, g, b)


class LineEmitter(Emitter):
    def __init__(self, x0: float, y0: float, x1: float, y1: float, speed: float = 0.0,
                 life: float = 2.0, color: RGB = (255, 255, 255)):
        self.x0, self.y0, self.x1, self.y1 = map(float, (x0, y0, x1, y1))
        self.speed = float(speed)
        self.life = float(life)
        self.color = color

    def emit_one(self, system: "ParticleSystemV1") -> Optional[Particle]:
        t = system.rng.rand()
        x = self.x0 + (self.x1 - self.x0) * t
        y = self.y0 + (self.y1 - self.y0) * t
        ang = system.rng.uniform(0.0, math.tau)
        vx = math.cos(ang) * self.speed
        vy = math.sin(ang) * self.speed
        seed = system.rng.randint(0, 2**31 - 1)
        r, g, b = self.color
        return Particle(x, y, vx, vy, self.life, seed, r, g, b)


class AreaEmitter(Emitter):
    def __init__(self, x0: float, y0: float, x1: float, y1: float, speed: float = 0.0,
                 life: float = 2.0, color: RGB = (255, 255, 255)):
        self.x0, self.y0, self.x1, self.y1 = map(float, (x0, y0, x1, y1))
        self.speed = float(speed)
        self.life = float(life)
        self.color = color

    def emit_one(self, system: "ParticleSystemV1") -> Optional[Particle]:
        x = system.rng.uniform(min(self.x0, self.x1), max(self.x0, self.x1))
        y = system.rng.uniform(min(self.y0, self.y1), max(self.y0, self.y1))
        ang = system.rng.uniform(0.0, math.tau)
        vx = math.cos(ang) * self.speed
        vy = math.sin(ang) * self.speed
        seed = system.rng.randint(0, 2**31 - 1)
        r, g, b = self.color
        return Particle(x, y, vx, vy, self.life, seed, r, g, b)


# Module function signature: (system, dt, t, signals) -> None
ParticleModule = Callable[["ParticleSystemV1", float, float, Dict[str, float]], None]


class ParticleSystemV1:
    def __init__(self, seed: int = 0, max_particles: int = 2000):
        self.seed = int(seed) & 0xFFFFFFFF
        self.rng = DeterministicRNG(self.seed)
        self.max_particles = int(max_particles)
        self.particles: List[Particle] = []
        self.modules: List[ParticleModule] = []

        # World constraints
        self.wrap_edges: bool = True
        self.friction: float = 0.0  # 0..1 (per second-ish)
        self.bounds: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)  # x0,y0,x1,y1

    # ---- serialization
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "max_particles": self.max_particles,
            "wrap_edges": self.wrap_edges,
            "friction": self.friction,
            "bounds": list(self.bounds),
            "particles": [p.to_dict() for p in self.particles],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ParticleSystemV1":
        sys = ParticleSystemV1(seed=int(d.get("seed", 0)), max_particles=int(d.get("max_particles", 2000)))
        sys.wrap_edges = bool(d.get("wrap_edges", True))
        sys.friction = float(d.get("friction", 0.0))
        b = d.get("bounds", [0, 0, 1, 1])
        if isinstance(b, (list, tuple)) and len(b) == 4:
            sys.bounds = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        sys.particles = [Particle.from_dict(p) for p in d.get("particles", [])]
        return sys

    # ---- bounds helpers
    def set_bounds_from_layout(self, layout: Dict[str, Any]) -> None:
        """
        Uses layout coords if available; otherwise uses matrix_w/h if present; otherwise defaults.
        """
        coords = layout.get("coords")
        if isinstance(coords, list) and coords:
            xs = [c[0] for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]
            ys = [c[1] for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]
            if xs and ys:
                self.bounds = (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
                return

        w = layout.get("matrix_w") or layout.get("w") or 1
        h = layout.get("matrix_h") or layout.get("h") or 1
        self.bounds = (0.0, 0.0, float(w - 1), float(h - 1))

    # ---- simulation
    def add_module(self, mod: ParticleModule) -> None:
        self.modules.append(mod)

    def step(self, dt: float, t: float = 0.0, signals: Optional[Dict[str, float]] = None) -> None:
        dt = float(dt)
        if dt <= 0:
            return
        signals = signals or {}

        # Apply modules (forces, fields, spawns, etc.)
        for mod in list(self.modules):
            mod(self, dt, float(t), signals)

        # Integrate + life
        x0, y0, x1, y1 = self.bounds
        keep: List[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            keep.append(p)

        # Apply shared integrator (drag/speed clamp/bounds)
        cfg = IntegratorConfigV1(
            friction=self.friction,
            speed_limit=self.speed_limit,
            wrap_edges=self.wrap_edges,
            bounds=(x0, y0, x1, y1),
        )
        euler_step_entities(keep, dt, cfg)

        self.particles = keep[: self.max_particles]


# ---- common modules

def module_constant_gravity(gx: float = 0.0, gy: float = 0.0) -> ParticleModule:
    gx, gy = float(gx), float(gy)
    def _mod(sys: ParticleSystemV1, dt: float, t: float, signals: Dict[str, float]) -> None:
        for p in sys.particles:
            p.vx += gx * dt
            p.vy += gy * dt
    return _mod


def module_radial_attractor(x: float, y: float, strength: float = 20.0, repel: bool = False,
                            falloff: float = 1.0, max_accel: float = 200.0) -> ParticleModule:
    cx, cy = float(x), float(y)
    strength = float(strength)
    falloff = max(0.0001, float(falloff))
    max_accel = float(max_accel)
    sign = -1.0 if repel else 1.0

    def _mod(sys: ParticleSystemV1, dt: float, t: float, signals: Dict[str, float]) -> None:
        for p in sys.particles:
            dx = cx - p.x
            dy = cy - p.y
            d2 = dx*dx + dy*dy + 1e-6
            inv = 1.0 / (d2 ** (0.5 * falloff))
            ax = dx * inv * strength * sign
            ay = dy * inv * strength * sign
            # clamp accel
            amag = math.hypot(ax, ay)
            if amag > max_accel:
                s = max_accel / amag
                ax *= s; ay *= s
            p.vx += ax * dt
            p.vy += ay * dt
    return _mod




def module_field_advection(field, strength: float = 1.0) -> ParticleModule:
    """Advect particles by a VectorField-like object (has sample(x,y,t)->(vx,vy))."""

    def _mod(sys: ParticleSystemV1, dt: float, t: float) -> None:
        for pt in sys.particles:
            vx, vy = field.sample(pt.x, pt.y, t)
            pt.vx += vx * strength * dt
            pt.vy += vy * strength * dt

    return _mod
def module_emit(emitter: Emitter, rate_per_sec: float = 10.0) -> ParticleModule:
    rate_per_sec = max(0.0, float(rate_per_sec))
    carry = {"acc": 0.0}

    def _mod(sys: ParticleSystemV1, dt: float, t: float, signals: Dict[str, float]) -> None:
        carry["acc"] += rate_per_sec * dt
        n = int(carry["acc"])
        if n > 0:
            carry["acc"] -= n
            emitter.emit(sys, n)
    return _mod