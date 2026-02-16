from __future__ import annotations
SHIPPED = True

import random
from typing import Dict, Any, List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save

USES = ["preview", "arduino"]


def _rgb_tuple(c: int) -> Tuple[int, int, int]:
    r = (c >> 16) & 0xFF
    g = (c >> 8) & 0xFF
    b = c & 0xFF
    return r, g, b


def _rand_non_white(rng: random.Random) -> Tuple[int, int, int]:
    while True:
        r = rng.randrange(256)
        g = rng.randrange(256)
        b = rng.randrange(256)
        if not (r == 255 and g == 255 and b == 255):
            return r, g, b


def _init_state(state: Dict[str, Any], num_leds: int, seed: int):
    state.clear()
    # RNG is persisted JSON-safely via behaviors.state helpers.
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["num_leds"] = num_leds
    state["snake_size"] = 1
    state["snake"] = [0]  # positions, head is last
    state["game_over"] = False
    state["food_pos"] = 0
    state["food_dir"] = 1
    state["_acc"] = 0.0
    state["flash_ticks"] = 0
    # colors
    rng = rng_load(state, seed=seed)
    body = _rand_non_white(rng)
    head = _rand_non_white(rng)
    # ensure different
    tries = 0
    while head == body and tries < 20:
        head = _rand_non_white(rng)
        tries += 1
    state["body"] = body
    state["head"] = head
    state["food"] = _rand_non_white(rng)
    _spawn_food(state)
    _determine_dir(state)
    rng_save(state, rng)


def _spawn_food(state: Dict[str, Any]):
    rng = rng_load(state, seed=int(state.get('seed', 1)))
    num_leds = int(state["num_leds"])
    snake: List[int] = state["snake"]
    # find a spot not on snake (bounded attempts)
    for _ in range(200):
        p = rng.randrange(num_leds)
        if p not in snake:
            state["food_pos"] = p
            break
    # new random food color (non-white, and ideally different)
    fc = _rand_non_white(rng)
    state["food"] = fc
    rng_save(state, rng)


def _determine_dir(state: Dict[str, Any]):
    num_leds = int(state["num_leds"])
    snake: List[int] = state["snake"]
    head = snake[-1] if snake else 0
    food = int(state["food_pos"])
    if food > head:
        state["food_dir"] = 1 if (food - head) <= (num_leds // 2) else -1
    else:
        state["food_dir"] = -1 if (head - food) <= (num_leds // 2) else 1


def _step(state: Dict[str, Any], t: float, params: Dict[str, Any]):
    if state.get("game_over"):
        # quick restart
        seed = int(params.get("seed", 1))
        _init_state(state, int(state.get("num_leds", 60)), seed)
        return

    num_leds = int(state["num_leds"])
    snake: List[int] = state["snake"]
    snake_size = int(state["snake_size"])
    food_pos = int(state["food_pos"])
    direction = int(state["food_dir"])

    head = snake[-1] if snake else 0
    nxt = head + direction
    if nxt >= num_leds:
        nxt = 0
    elif nxt < 0:
        nxt = num_leds - 1

    # eat?
    if nxt == food_pos:
        snake_size += 1
        state["snake_size"] = snake_size
        # body becomes food color
        state["body"] = tuple(state["food"])
        _spawn_food(state)
        _determine_dir(state)
        # flash briefly
        flash_ms = float(params.get("flash_ms", 50.0))
        # Flash is represented as a tick counter to keep it deterministic.
        state["flash_ticks"] = max(0, int((flash_ms / 1000.0) / max(1e-6, float(params.get('_fixed_dt', 1/60)))) )

    # advance snake: append new head, then trim tail to size
    snake.append(nxt)
    if len(snake) > snake_size:
        # keep last snake_size
        state["snake"] = snake[-snake_size:]
        snake = state["snake"]

    # collision with self (head in body)
    head = snake[-1]
    if head in snake[:-1]:
        state["game_over"] = True


def _render(num_leds: int, state: Dict[str, Any], t: float, params: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    out = [(0, 0, 0)] * int(num_leds)
    snake: List[int] = state["snake"]
    snake_size = int(state["snake_size"])
    body = tuple(state["body"])
    head = tuple(state["head"])
    food = tuple(state["food"])
    food_pos = int(state["food_pos"])

    # draw body gradient
    if snake_size <= 1:
        if snake:
            out[snake[-1]] = head
    else:
        for i, pos in enumerate(snake):
            if i == len(snake) - 1:
                out[pos] = head
            else:
                # gradient scale 0..255
                gv = int(i * 255 / max(1, (len(snake) - 1)))
                out[pos] = (body[0] * gv // 255, body[1] * gv // 255, body[2] * gv // 255)

    # food
    if 0 <= food_pos < num_leds:
        out[food_pos] = food

    # optional flash overlay (tint head)
    if int(state.get("flash_ticks", 0) or 0) > 0:
        if snake:
            out[snake[-1]] = (255, 0, 0)
    return out


def _update(*, state: Dict[str, Any], params: Dict[str, Any], dt: float, t: float, audio=None):
    """Fixed-tick update driven by PreviewEngine's SimClock."""
    params = params or {}
    seed = int(params.get("seed", 1))
    n = int(params.get('_num_leds', state.get('num_leds', 60) or 60))
    if int(state.get('num_leds', -1)) != int(n) or "snake" not in state or int(state.get("seed", -1)) != (seed & 0xFFFFFFFF):
        # Init on first tick or when layout/seed changes.
        _init_state(state, int(n), seed)

    speed = float(params.get("speed", 70.0))  # moves per second-ish
    if speed <= 1.0:
        speed = 1.0
    acc = float(state.get("_acc", 0.0) or 0.0)
    acc += float(dt)
    step_interval = 1.0 / speed
    steps = 0
    while acc >= step_interval and steps < 8:
        _step(state, float(t), params)
        acc -= step_interval
        steps += 1
    state["_acc"] = float(acc)

    # Tick down flash.
    ft = int(state.get("flash_ticks", 0) or 0)
    if ft > 0:
        state["flash_ticks"] = ft - 1


def _preview_emit(*, num_leds: int, params: dict, t: float, state=None):
    if state is None:
        state = {}
    params = params or {}
    seed = int(params.get("seed", 1))
    if state.get("num_leds") != int(num_leds) or "snake" not in state or int(state.get("seed", -1)) != (seed & 0xFFFFFFFF):
        _init_state(state, int(num_leds), seed)
    return _render(int(num_leds), state, float(t), params)


def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    # Not yet integrated into the multi-layer Arduino emitter pipeline.
    raise RuntimeError("Snake (Game) is preview-ready but Arduino export is not wired yet.")


def register_snake_game():
    defn = BehaviorDef(
        "snake_game",
        title="Snake (Game)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = _update
    register(defn)