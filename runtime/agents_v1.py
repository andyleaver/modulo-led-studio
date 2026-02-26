from __future__ import annotations

"""Agent System V1

A reusable, deterministic agent framework intended to sit *above* runtime.entities.

Design goals
- Reuse existing Entity stepping/collision primitives (do not duplicate).
- Provide a stable neighbor-query API (grid hash) for flock/crowd/agent behaviors.
- Keep everything export-safe/deterministic (no hidden global RNG; caller supplies seeds).

This module is intentionally generic; concrete behaviors live in behaviors/effects/*.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
import math

from runtime.entities import Entity, step_entities


@dataclass
class Agent:
    """An Agent is an Entity with lightweight intent/state.

    We deliberately keep this small and numeric. Rich state should live in an
    external state dict keyed by agent index/id for export parity.
    """

    ent: Entity
    # optional metadata
    team: int = 0
    heading: float = 0.0
    energy: float = 1.0
    # scratch / behavior-specific small state
    mem: Dict[str, float] = field(default_factory=dict)


def as_entity(a: Agent) -> Entity:
    return a.ent


class AgentWorldV1:
    """Spatial hashing + world constraints for agents."""

    def __init__(
        self,
        *,
        bounds: Tuple[float, float] = (1.0, 1.0),
        wrap: bool = True,
        cell_size: float = 0.12,
    ) -> None:
        self.bounds = (float(bounds[0]), float(bounds[1]))
        self.wrap = bool(wrap)
        self.cell_size = float(cell_size) if float(cell_size) > 1e-6 else 0.12
        self._grid: Dict[Tuple[int, int], List[int]] = {}
        self._last_agents_n: int = 0

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        cs = self.cell_size
        return (int(math.floor(x / cs)), int(math.floor(y / cs)))

    def rebuild_grid(self, agents: List[Agent]) -> None:
        self._grid.clear()
        for idx, a in enumerate(agents):
            e = a.ent
            if not e.alive:
                continue
            c = self._cell(e.x, e.y)
            self._grid.setdefault(c, []).append(idx)
        self._last_agents_n = len(agents)

    def iter_neighbor_indices(self, agents: List[Agent], idx: int, radius: float) -> Iterable[int]:
        """Yield indices of potential neighbors within radius.

        Uses a 2D grid hash. Caller should still filter by exact distance.
        """
        if idx < 0 or idx >= len(agents):
            return []
        r = float(radius)
        if r <= 0.0:
            return []

        e = agents[idx].ent
        cs = self.cell_size
        if cs <= 1e-6:
            return []

        cx, cy = self._cell(e.x, e.y)
        cr = int(math.ceil(r / cs))

        out: List[int] = []
        for gx in range(cx - cr, cx + cr + 1):
            for gy in range(cy - cr, cy + cr + 1):
                ids = self._grid.get((gx, gy))
                if not ids:
                    continue
                out.extend(ids)
        return out

    def delta(self, a: Entity, b: Entity) -> Tuple[float, float]:
        """Vector from a->b respecting wrap."""
        dx = b.x - a.x
        dy = b.y - a.y
        if self.wrap:
            w, h = self.bounds
            if dx > w / 2:
                dx -= w
            if dx < -w / 2:
                dx += w
            if dy > h / 2:
                dy -= h
            if dy < -h / 2:
                dy += h
        return dx, dy


# --- steering primitives ---

def _limit(vx: float, vy: float, max_mag: float) -> Tuple[float, float]:
    m = math.hypot(vx, vy)
    if m <= 1e-9:
        return 0.0, 0.0
    if m <= max_mag:
        return vx, vy
    s = max_mag / m
    return vx * s, vy * s


def steer_seek(world: AgentWorldV1, agent: Agent, target_xy: Tuple[float, float], *, weight: float = 1.0) -> Tuple[float, float]:
    e = agent.ent
    tx, ty = float(target_xy[0]), float(target_xy[1])
    dummy = Entity("t", tx, ty, 0.0, 0.0, 0.0)
    dx, dy = world.delta(e, dummy)
    return dx * float(weight), dy * float(weight)


def steer_flee(world: AgentWorldV1, agent: Agent, threat_xy: Tuple[float, float], *, weight: float = 1.0) -> Tuple[float, float]:
    ax, ay = steer_seek(world, agent, threat_xy, weight=weight)
    return -ax, -ay


def steer_wander(agent: Agent, *, t: float, strength: float = 1.0, freq: float = 1.0, seed: int = 0) -> Tuple[float, float]:
    """Deterministic wander using sin/cos (seeded phase offset)."""
    s = float(strength)
    f = float(freq)
    ph = (seed & 0xFFFF) * 0.0001
    a = (float(t) * f) + ph + float(agent.team) * 0.17
    return math.cos(a) * s, math.sin(a * 1.13) * s


def steer_boids_v1(
    world: AgentWorldV1,
    agents: List[Agent],
    idx: int,
    *,
    radius: float,
    sep: float,
    align: float,
    cohesion: float,
    sep_dist: Optional[float] = None,
) -> Tuple[float, float]:
    """Compute a classic boids steering acceleration for agent idx."""

    if idx < 0 or idx >= len(agents):
        return 0.0, 0.0

    a = agents[idx].ent
    if not a.alive:
        return 0.0, 0.0

    r = float(radius)
    r2 = r * r
    sd = float(sep_dist) if sep_dist is not None else (r * 0.35)
    sd2 = sd * sd

    # accumulators
    n = 0
    ax = ay = 0.0  # alignment (avg vel)
    cx = cy = 0.0  # cohesion (avg pos)
    sx = sy = 0.0  # separation

    cand = world.iter_neighbor_indices(agents, idx, r)
    for j in cand:
        if j == idx:
            continue
        b = agents[j].ent
        if not b.alive:
            continue
        dx, dy = world.delta(a, b)
        d2 = dx * dx + dy * dy
        if d2 <= 1e-9 or d2 > r2:
            continue
        n += 1
        ax += b.vx
        ay += b.vy
        cx += dx
        cy += dy
        if d2 < sd2:
            inv = 1.0 / max(1e-6, d2)
            sx -= dx * inv
            sy -= dy * inv

    if n <= 0:
        return 0.0, 0.0

    invn = 1.0 / float(n)
    ax *= invn
    ay *= invn
    cx *= invn
    cy *= invn

    # alignment steers towards avg velocity
    outx = (ax - a.vx) * float(align)
    outy = (ay - a.vy) * float(align)

    # cohesion steers towards neighbors' center (use avg delta)
    outx += cx * float(cohesion) * 0.5
    outy += cy * float(cohesion) * 0.5

    # separation steers away when too close
    outx += sx * float(sep) * 0.35
    outy += sy * float(sep) * 0.35

    return outx, outy


def integrate_agents_v1(
    world: AgentWorldV1,
    agents: List[Agent],
    *,
    dt: float,
    max_speed: float = 0.45,
    max_accel: float = 1.25,
    accels: Optional[List[Tuple[float, float]]] = None,
) -> None:
    """Apply accelerations to agent velocities, clamp, then step positions."""

    if accels is None:
        accels = [(0.0, 0.0)] * len(agents)

    for i, ag in enumerate(agents):
        e = ag.ent
        if not e.alive:
            continue
        ax, ay = accels[i] if i < len(accels) else (0.0, 0.0)
        ax, ay = _limit(float(ax), float(ay), float(max_accel))
        e.vx += ax * float(dt)
        e.vy += ay * float(dt)

        e.vx, e.vy = _limit(e.vx, e.vy, float(max_speed))

        # heading is derived from velocity when moving
        if (e.vx * e.vx + e.vy * e.vy) > 1e-8:
            ag.heading = math.atan2(e.vy, e.vx)

    # reuse existing entity stepping (no duplication)
    step_entities([a.ent for a in agents], float(dt), bounds=world.bounds, wrap=world.wrap)


def make_agents_v1(
    *,
    count: int,
    bounds: Tuple[float, float] = (1.0, 1.0),
    seed: int = 1337,
    speed: float = 0.20,
    r: float = 0.02,
    team_count: int = 1,
) -> List[Agent]:
    """Deterministic initial agent set."""
    import random

    w, h = float(bounds[0]), float(bounds[1])
    c = 1 if count < 1 else int(count)
    rng = random.Random(int(seed) & 0xFFFFFFFF)

    out: List[Agent] = []
    for i in range(c):
        x = rng.random() * w
        y = rng.random() * h
        ang = rng.random() * math.tau
        vx = math.cos(ang) * float(speed)
        vy = math.sin(ang) * float(speed)
        team = (i % max(1, int(team_count)))
        ent = Entity("agent", x, y, vx, vy, float(r), True, 999.0)
        out.append(Agent(ent=ent, team=team, heading=ang, energy=1.0, mem={}))
    return out
