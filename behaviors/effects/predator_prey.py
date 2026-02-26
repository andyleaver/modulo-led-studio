from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional
import math
import random

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]
USES = ["pp_speed", "pp_fear_radius", "pp_strip_width"]


# Implemented on top of runtime.agents_v1 + runtime.entities (no bespoke stepping).
from runtime.agents_v1 import Agent, AgentWorldV1, steer_flee, steer_seek, steer_wander
from runtime.entities import Entity, step_entities


def _clamp8(x: float) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))


def _dims(num_leds: int, params: Dict[str, Any]) -> Tuple[int, int]:
    mw = int(params.get("_mw", 0) or 0)
    mh = int(params.get("_mh", 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(num_leds):
        return mw, mh
    w = int(params.get("pp_strip_width", 32) or 32)
    if w < 1:
        w = 1
    h = max(1, int(num_leds) // w)
    if w * h < 1:
        return max(1, int(num_leds)), 1
    return w, h


def _idx(x: int, y: int, w: int, h: int) -> int:
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
    # Firmware implementation is embedded in the core exporter (beh_id == 19).
    # Exporter maps pp_speed into the generic 'speed' channel.
    return ""


class PredatorPrey:
    """A tiny 'world' behavior.

    - Prey wanders but flees if predator is within radius.
    - Predator chases prey.
    - When predator catches prey, prey respawns and score increments.

    This is deliberately NOT an 'effect' — it's a minimal agent system.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 256) or 256)
        w, h = _dims(n, params)
        seed = int(params.get("seed", 4242) or 4242) & 0xFFFFFFFF
        rng = random.Random(seed)

        state.clear()
        state["w"] = int(w)
        state["h"] = int(h)
        state["score"] = 0

        # Two agents sharing a common agent framework.
        px = rng.random() * (w - 1 if w > 1 else 1)
        py = rng.random() * (h - 1 if h > 1 else 1)
        rx = rng.random() * (w - 1 if w > 1 else 1)
        ry = rng.random() * (h - 1 if h > 1 else 1)
        prey_ent = Entity("prey", float(px), float(py), 0.0, 0.0, 0.20, True, 999.0)
        pred_ent = Entity("pred", float(rx), float(ry), 0.0, 0.0, 0.22, True, 999.0)
        state["agents"] = [Agent(ent=prey_ent, team=0), Agent(ent=pred_ent, team=1)]
        state["trail"] = [0.0] * (w * h)
        state["rng_seed"] = seed

    def _respawn_prey(self, state: Dict[str, Any]) -> None:
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        seed = int(state.get("rng_seed", 1) or 1) + int(state.get("score", 0) or 0) * 17
        rng = random.Random(seed)
        agents = state.get("agents")
        if isinstance(agents, list) and len(agents) >= 2 and isinstance(agents[0], Agent):
            prey = agents[0]
            prey.ent.x = rng.random() * (w - 1 if w > 1 else 1)
            prey.ent.y = rng.random() * (h - 1 if h > 1 else 1)
            prey.ent.vx = 0.0
            prey.ent.vy = 0.0
            return
        # fallback: full reset
        self.reset(state, params={"_num_leds": w * h, "pp_strip_width": w, "seed": int(state.get("rng_seed", 0) or 0)})

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        agents = state.get("agents")
        if not (isinstance(agents, list) and len(agents) >= 2 and isinstance(agents[0], Agent) and isinstance(agents[1], Agent)):
            self.reset(state, params=params)
            agents = state.get("agents")

        if not (isinstance(agents, list) and len(agents) >= 2 and isinstance(agents[0], Agent) and isinstance(agents[1], Agent)):
            return

        prey = agents[0]
        pred = agents[1]

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)

        world = AgentWorldV1(bounds=(float(w), float(h)), wrap=True, cell_size=1.0)
        speed = float(params.get("pp_speed", 10.0) or 10.0)
        speed = 0.5 if speed < 0.5 else (60.0 if speed > 60.0 else speed)

        fear = float(params.get("pp_fear_radius", 6.0) or 6.0)
        fear = 1.0 if fear < 1.0 else (30.0 if fear > 30.0 else fear)
        fear2 = fear * fear

        trail = state.get("trail")
        if not isinstance(trail, list) or len(trail) != w * h:
            trail = [0.0] * (w * h)
            state["trail"] = trail
        # decay trail
        for i in range(len(trail)):
            trail[i] *= 0.93

        px, py = prey.ent.x, prey.ent.y
        rx, ry = pred.ent.x, pred.ent.y

        dx = px - rx
        dy = py - ry
        d2 = dx * dx + dy * dy

        wx, wy = steer_wander(prey, t=float(t), strength=0.9, freq=0.9, seed=int(state.get("rng_seed", 0) or 0))
        fx = fy = 0.0
        if d2 < fear2 and d2 > 1e-9:
            f = max(0.0, min(1.0, (fear2 - d2) / max(1e-6, fear2)))
            fx, fy = steer_flee(world, prey, (rx, ry), weight=3.8 * f)

        cx, cy = steer_seek(world, pred, (px, py), weight=3.2)

        prey.ent.vx += (wx + fx) * float(dt)
        prey.ent.vy += (wy + fy) * float(dt)
        pred.ent.vx += cx * float(dt)
        pred.ent.vy += cy * float(dt)

        def _clamp_vel(e: Entity, vmax: float) -> None:
            m = math.hypot(e.vx, e.vy)
            if m > vmax and m > 1e-9:
                s = vmax / m
                e.vx *= s
                e.vy *= s

        _clamp_vel(prey.ent, float(speed) * 0.65)
        _clamp_vel(pred.ent, float(speed))

        step_entities([prey.ent, pred.ent], float(dt), bounds=(float(w), float(h)), wrap=True)

        # trails
        px, py = prey.ent.x, prey.ent.y
        rx, ry = pred.ent.x, pred.ent.y
        ip = _idx(int(round(px)), int(round(py)), w, h)
        ir = _idx(int(round(rx)), int(round(ry)), w, h)
        trail[ip] = min(1.0, trail[ip] + 0.35)
        trail[ir] = min(1.0, trail[ir] + 0.6)

        # catch
        # treat as capture within 1.2 cells
        cdx = px - rx
        cdy = py - ry
        if (cdx * cdx + cdy * cdy) < 1.44:
            state["score"] = int(state.get("score", 0) or 0) + 1
            self._respawn_prey(state)

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        trail = state.get("trail")
        if not isinstance(trail, list) or len(trail) != w * h:
            trail = [0.0] * (w * h)
            state["trail"] = trail

        out: List[RGB] = [(0, 0, 0)] * n

        # background from trail
        for i in range(min(n, w * h)):
            v = float(trail[i] or 0.0)
            v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
            # dim purple haze
            out[i] = (_clamp8(60 * v), _clamp8(20 * v), _clamp8(80 * v))

        agents = state.get("agents")
        if isinstance(agents, list) and len(agents) >= 2 and isinstance(agents[0], Agent) and isinstance(agents[1], Agent):
            prey = agents[0]
            pred = agents[1]
            i = _idx(int(round(float(prey.ent.x))), int(round(float(prey.ent.y))), w, h)
            if i < n:
                out[i] = (40, 255, 80)  # prey green
            i = _idx(int(round(float(pred.ent.x))), int(round(float(pred.ent.y))), w, h)
            if i < n:
                out[i] = (255, 40, 40)  # predator red

        return out


def _preview_emit(*, num_leds: int, params: dict, t: float, state: dict, dt: float, audio: Optional[dict] = None) -> List[RGB]:
    fx = PredatorPrey()
    if not state:
        fx.reset(state, params=params)
    fx.tick(state, params=params, dt=dt, t=t, audio=audio)
    return fx.render(num_leds=num_leds, params=params, t=t, state=state)


def register_predator_prey():
    bd = BehaviorDef(
        "predator_prey",
        title="Predator / Prey",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    return register(bd)
