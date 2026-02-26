from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional
import math

from runtime.agents_v1 import Agent, AgentWorldV1, make_agents_v1, steer_boids_v1, steer_wander, integrate_agents_v1

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]
USES = ["boids_count", "boids_speed", "boids_sep", "boids_align", "boids_cohesion", "boids_trail", "boids_strip_width", "seed"]


def _clamp8(x: float) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))


def _fold_dims(num_leds: int, params: Dict[str, Any]) -> Tuple[int, int]:
    mw = int(params.get("_mw", 0) or 0)
    mh = int(params.get("_mh", 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(num_leds):
        return mw, mh
    w = int(params.get("boids_strip_width", 32) or 32)
    if w < 1:
        w = 1
    h = max(1, int(num_leds) // w)
    if w * h < 1:
        return max(1, int(num_leds)), 1
    return w, h


def _idx(x: int, y: int, w: int, h: int) -> int:
    # clamp
    if x < 0:
        x = 0
    elif x >= w:
        x = w - 1
    if y < 0:
        y = 0
    elif y >= h:
        y = h - 1
    return y * w + x


def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    # Firmware implementation is embedded in the core exporter (beh_id == 18).
    # Exporter maps boids-specific params into generic channels (speed/width/density).
    return ""


class BoidsSwarm:
    """Simple boids/swarm behavior.

    NOTE: Refactored to use runtime.agents_v1 so we don't duplicate neighbor loops.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 256) or 256)
        w, h = _fold_dims(n, params)

        count = int(params.get("boids_count", 10) or 10)
        count = 1 if count < 1 else (128 if count > 128 else count)

        seed = int(params.get("seed", 1337) or 1337) & 0xFFFFFFFF

        # Create deterministic agents in grid space (0..w, 0..h)
        agents = make_agents_v1(count=count, bounds=(float(w), float(h)), seed=seed, speed=0.35, r=0.25)

        # World: cell size will be tuned each tick based on radius
        world = AgentWorldV1(bounds=(float(w), float(h)), wrap=True, cell_size=2.0)

        state.clear()
        state["w"] = int(w)
        state["h"] = int(h)
        state["agents"] = agents
        state["world"] = world
        state["heat"] = [0.0] * (w * h)

    def tick(
        self,
        state: Dict[str, Any],
        *,
        params: Dict[str, Any],
        dt: float,
        t: float,
        audio: Optional[dict] = None,
    ) -> None:
        agents = state.get("agents")
        world = state.get("world")
        if not isinstance(agents, list) or not agents or world is None:
            self.reset(state, params=params)
            agents = state.get("agents")
            world = state.get("world")

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)

        # --- params ---
        speed = float(params.get("boids_speed", 6.0) or 6.0)
        speed = 0.2 if speed < 0.2 else (40.0 if speed > 40.0 else speed)

        sep_k = float(params.get("boids_sep", 1.2) or 1.2)
        align_k = float(params.get("boids_align", 0.8) or 0.8)
        coh_k = float(params.get("boids_cohesion", 0.6) or 0.6)

        # neighborhood radius scales with grid (same heuristic as before)
        r = max(2.0, min(float(max(w, h)) * 0.18, 10.0))

        # Tune spatial hash cell size for this radius (deterministic)
        try:
            world.bounds = (float(w), float(h))
            world.cell_size = max(1.0, float(r) * 0.60)
        except Exception:
            pass

        # heat trail
        heat = state.get("heat")
        if not isinstance(heat, list) or len(heat) != w * h:
            heat = [0.0] * (w * h)
            state["heat"] = heat
        trail = float(params.get("boids_trail", 0.92) or 0.92)
        trail = 0.0 if trail < 0.0 else (0.999 if trail > 0.999 else trail)
        for i in range(len(heat)):
            heat[i] *= trail

        # rebuild neighbor grid once per tick
        world.rebuild_grid(agents)

        # compute boids accelerations
        accels: List[Tuple[float, float]] = []
        seed = int(params.get("seed", 1337) or 1337) & 0xFFFFFFFF
        for i in range(len(agents)):
            ax, ay = steer_boids_v1(
                world,
                agents,
                i,
                radius=r,
                sep=sep_k,
                align=align_k,
                cohesion=coh_k,
                sep_dist=r * 0.35,
            )
            # small deterministic wander so empty neighborhoods still move
            wx, wy = steer_wander(agents[i], t=t, strength=0.18, freq=0.9, seed=seed)
            ax += wx
            ay += wy
            accels.append((ax, ay))

        # integrate with clamped speed/accel (grid units)
        integrate_agents_v1(world, agents, dt=float(dt), max_speed=float(speed), max_accel=float(speed) * 0.85, accels=accels)

        # deposit heat at each agent position
        for ag in agents:
            e = ag.ent
            ix = int(round(float(e.x)))
            iy = int(round(float(e.y)))
            heat[_idx(ix, iy, w, h)] = min(1.0, float(heat[_idx(ix, iy, w, h)]) + 0.35)

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        heat = state.get("heat")
        if not isinstance(heat, list) or len(heat) != w * h:
            heat = [0.0] * (w * h)
            state["heat"] = heat

        out: List[RGB] = [(0, 0, 0)] * n

        # palette: deep blue -> cyan -> white
        for i in range(min(n, w * h)):
            v = float(heat[i] or 0.0)
            v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
            r = _clamp8(255.0 * (v ** 2.2))
            g = _clamp8(255.0 * (v ** 1.1))
            b = _clamp8(255.0 * (0.25 + 0.75 * v))
            out[i] = (r, g, b)

        return out


def _preview_emit(*, num_leds: int, params: dict, t: float, state: dict, dt: float, audio: Optional[dict] = None, **_kwargs) -> List[RGB]:
    fx = BoidsSwarm()
    if not state:
        fx.reset(state, params=params)
    fx.tick(state, params=params, dt=dt, t=t, audio=audio)
    return fx.render(num_leds=num_leds, params=params, t=t, state=state)


def register_boids_swarm():
    bd = BehaviorDef(
        "boids_swarm",
        title="Boids Swarm",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    return register(bd)
