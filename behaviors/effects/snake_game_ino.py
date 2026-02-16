from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save
from behaviors.stateful_adapter import StatefulEffect, AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]
USES = ["snake_speed"]

def _clamp8(x: int) -> int:
    return 0 if x < 0 else (255 if x > 255 else int(x))

def _map_int(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    if in_max == in_min:
        return out_min
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

class SnakeGameINO(StatefulEffect):
    """Faithful port of the first sketch section in 'game visuals.ino' (Snake)."""

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 288) or 288)
        seed = int(params.get("seed", 1)) & 0xFFFFFFFF
        state.clear()
        state["_n"] = n
        state["seed"] = seed
        state["snakeSize"] = 1

        # IMPORTANT: The original Arduino sketch stores the snake in a fixed-size
        # `int snakePositions[PIXEL_COUNT]` buffer and updates it in a slightly
        # unusual way:
        #   snakePositions[snakeSize] = next;
        #   for i=0..snakeSize-1: snakePositions[i] = snakePositions[i+1];
        #
        # That means when the snake grows, newly exposed slots contain their
        # prior default values (globals -> 0 on Arduino), which changes the
        # on-strip look compared to a "correct" queue implementation.
        #
        # To match the sketch's visuals, we keep a fixed-length array and apply
        # the same write+shift semantics.
        state["snakePositions"] = [0] * n
        state["foodPosition"] = 0
        state["gameOver"] = False
        state["foodDirection"] = 1
        state["interval_ms"] = int(1000 / 70)  # INITIAL_SPEED = 70
        state["_acc_ms"] = 0.0
        state["bodyColor"] = (0, 255, 0)
        state["headColor"] = (255, 0, 0)
        state["foodColor"] = (0, 0, 255)
        state["shouldChangeColor"] = False
        state["isFlashing"] = False

        rng = rng_load(state, seed=seed)
        # Equivalent order from Arduino setup(): clearDisplay, spawnFood, determineFoodDirection, setInitialColors, drawSnake
        self._spawn_food(state, rng=rng)
        self._determine_food_direction(state)
        self._set_initial_colors(state, rng=rng)
        rng_save(state, rng)

    
    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        # If running on a matrix layout, run a classic autonomous Snake in 2D.
        n = int(params.get("_num_leds", state.get("_n", 0) or 0) or state.get("_n", 0) or 0)
        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)
        is_matrix = (mw > 1 and mh > 1 and (mw * mh) == int(n or (mw * mh)))

        if is_matrix:
            if not state.get("_matrix_snake", False):
                self._matrix_init(state, mw=mw, mh=mh, params=params)
            snake_speed = float(params.get("snake_speed", 8.0) or 8.0)
            if snake_speed <= 0.1:
                snake_speed = 0.1
            interval_ms = int(max(10.0, 1000.0 / snake_speed))
            acc = float(state.get("_acc_ms", 0.0) or 0.0) + float(dt) * 1000.0
            steps = 0
            while acc >= interval_ms and steps < 8:
                acc -= interval_ms
                self._matrix_step(state, mw=mw, mh=mh, params=params)
                steps += 1
            state["_acc_ms"] = acc
            return

        # ---- Strip / 1D behavior (keep legacy INO-ish movement) ----
        if bool(state.get("gameOver", False)):
            self._restart_game(state, params=params)
            return

        snake_speed = float(params.get("snake_speed", 8.0) or 8.0)
        if snake_speed <= 0.1:
            snake_speed = 0.1
        interval_ms = int(max(10.0, 1000.0 / snake_speed))
        acc = float(state.get("_acc_ms", 0.0) or 0.0) + float(dt) * 1000.0

        # Keep step count bounded in case of long dt.
        steps = 0
        while acc >= interval_ms and steps < 8:
            acc -= interval_ms
            self._move_snake(state, params=params)
            self._check_collision(state)
            if bool(state.get("gameOver", False)):
                break
            steps += 1

        state["_acc_ms"] = acc
    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        px: List[RGB] = [(0, 0, 0)] * n

        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)
        if bool(state.get("_matrix_snake", False)) and mw > 1 and mh > 1 and (mw * mh) == n:
            body: List[int] = list(state.get("m_body", []) or [])
            food = int(state.get("m_food", 0) or 0) % n
            # colors (simple, game-like)
            body_col = (0, 200, 0)
            head_col = (200, 40, 40)
            food_col = (40, 120, 220)

            # draw body
            for p in body[:-1]:
                px[int(p) % n] = body_col
            if body:
                px[int(body[-1]) % n] = head_col
            px[food] = food_col
            return px

        snakeSize = int(state.get("snakeSize", 1) or 1)
        buf = list(state.get("snakePositions", []) or [])
        if len(buf) < n:
            buf = (buf + [0] * n)[:n]
        # Arduino draws snakePositions[0..snakeSize-1]
        snake = buf[:max(1, min(snakeSize, n))]
        body = tuple(state.get("bodyColor", (0, 255, 0)))
        head = tuple(state.get("headColor", (255, 0, 0)))
        food_pos = int(state.get("foodPosition", 0) or 0) % n
        food = tuple(state.get("foodColor", (255, 255, 255)))

        # drawSnake() with gradient mapping
        for i in range(min(snakeSize, len(snake))):
            pos = int(snake[i]) % n
            if i == snakeSize - 1:
                px[pos] = (int(head[0]) & 255, int(head[1]) & 255, int(head[2]) & 255)
            else:
                gv = _map_int(i, 0, max(1, snakeSize - 1), 0, 255)
                r = _clamp8(int(body[0]) * gv // 255)
                g = _clamp8(int(body[1]) * gv // 255)
                b = _clamp8(int(body[2]) * gv // 255)
                px[pos] = (r, g, b)

        # drawFood()
        px[food_pos] = (int(food[0]) & 255, int(food[1]) & 255, int(food[2]) & 255)

        # drawSnake() in Arduino resets isFlashing false after drawing once
        if bool(state.get("isFlashing", False)):
            state["isFlashing"] = False

        return px

    
    # ===== Matrix autonomous snake (preview-only) =====

    def _matrix_init(self, state: Dict[str, Any], *, mw: int, mh: int, params: Dict[str, Any]) -> None:
        n = int(mw * mh)
        seed = int(params.get("seed", state.get("seed", 1))) & 0xFFFFFFFF
        state["_matrix_snake"] = True
        state["m_w"] = int(mw)
        state["m_h"] = int(mh)
        state["m_n"] = int(n)
        # Start near center, length 3 heading right
        cx, cy = mw // 2, mh // 2
        start = cy * mw + cx
        body = [start - 2, start - 1, start]
        body = [p for p in body if 0 <= p < n]
        if len(body) < 2:
            body = [start]
        state["m_body"] = body  # tail -> head
        state["m_dir"] = (1, 0)  # dx, dy
        rng = rng_load(state, seed=seed)
        state["seed"] = seed
        state["m_rng_seeded"] = True
        # Spawn first food not on snake
        self._matrix_spawn_food(state, mw=mw, mh=mh, rng=rng)
        rng_save(state, rng)

    def _matrix_spawn_food(self, state: Dict[str, Any], *, mw: int, mh: int, rng) -> None:
        n = int(mw * mh)
        body = set(int(p) for p in (state.get("m_body") or []))
        for _ in range(500):
            p = int(rng.randrange(n))
            if p not in body:
                state["m_food"] = p
                return
        # fallback
        state["m_food"] = 0

    def _matrix_step(self, state: Dict[str, Any], *, mw: int, mh: int, params: Dict[str, Any]) -> None:
        # Simple autonomous snake: BFS path to food avoiding body (tail is allowed because it moves).
        n = int(mw * mh)
        body: List[int] = list(state.get("m_body", []) or [])
        if not body:
            self._matrix_init(state, mw=mw, mh=mh, params=params)
            body = list(state.get("m_body", []) or [])
        head = int(body[-1]) % n
        food = int(state.get("m_food", 0) or 0) % n

        # Build obstacle set: all body except tail (since tail will move unless we grow)
        obstacles = set(int(p) for p in body[1:])  # allow current tail
        next_cell = self._matrix_next_via_bfs(head, food, obstacles, mw=mw, mh=mh)

        if next_cell is None:
            # No path: pick any safe move (avoid full body, no wrap)
            obstacles2 = set(int(p) for p in body[:-1])
            next_cell = self._matrix_pick_safe_neighbor(head, obstacles2, state, mw=mw, mh=mh)

        if next_cell is None:
            # Stuck: restart
            self._matrix_init(state, mw=mw, mh=mh, params=params)
            return

        grew = (next_cell == food)
        body.append(next_cell)

        if grew:
            # increase speed slightly like a game (bounded)
            snake_speed = float(params.get("snake_speed", 8.0) or 8.0)
            if snake_speed <= 0.1:
                snake_speed = 0.1
            interval_ms = int(max(10.0, 1000.0 / snake_speed))
            state["interval_ms"] = max(6, interval_ms - 1)
            rng = rng_load(state, seed=int(state.get("seed", 1)))
            self._matrix_spawn_food(state, mw=mw, mh=mh, rng=rng)
            rng_save(state, rng)
        else:
            # move tail forward
            body.pop(0)

        # If collision (should be avoided, but just in case), restart
        if len(set(body)) != len(body):
            self._matrix_init(state, mw=mw, mh=mh, params=params)
            return

        state["m_body"] = body

    def _matrix_neighbors(self, cell: int, *, mw: int, mh: int):
        x, y = cell % mw, cell // mw
        if x > 0:
            yield cell - 1
        if x < mw - 1:
            yield cell + 1
        if y > 0:
            yield cell - mw
        if y < mh - 1:
            yield cell + mw

    def _matrix_next_via_bfs(self, start: int, goal: int, obstacles: set, *, mw: int, mh: int):
        if start == goal:
            return start
        from collections import deque
        q = deque([start])
        prev = {start: None}
        while q:
            cur = q.popleft()
            for nb in self._matrix_neighbors(cur, mw=mw, mh=mh):
                if nb in prev:
                    continue
                if nb in obstacles:
                    continue
                prev[nb] = cur
                if nb == goal:
                    q.clear()
                    break
                q.append(nb)
        if goal not in prev:
            return None
        # walk back one step from goal to start
        cur = goal
        while prev[cur] is not None and prev[cur] != start:
            cur = prev[cur]
        return cur if prev[cur] == start else (goal if prev[cur] == start else None)

    def _matrix_pick_safe_neighbor(self, head: int, obstacles: set, state: Dict[str, Any], *, mw: int, mh: int):
        # Prefer continuing direction if safe, else any safe neighbor.
        dx, dy = state.get("m_dir", (1, 0))
        # compute forward
        x, y = head % mw, head // mw
        fx, fy = x + int(dx), y + int(dy)
        forward = None
        if 0 <= fx < mw and 0 <= fy < mh:
            forward = fy * mw + fx
        if forward is not None and forward not in obstacles:
            return forward
        # else pick neighbor with max free space heuristic (degree)
        best = None
        best_score = -1
        for nb in self._matrix_neighbors(head, mw=mw, mh=mh):
            if nb in obstacles:
                continue
            score = 0
            for nb2 in self._matrix_neighbors(nb, mw=mw, mh=mh):
                if nb2 not in obstacles:
                    score += 1
            if score > best_score:
                best_score = score
                best = nb
        return best
# ===== Arduino function ports =====

    def _move_snake(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", state.get("_n", 1)) or state.get("_n", 1))
        snakeSize = int(state.get("snakeSize", 1) or 1)
        buf = list(state.get("snakePositions", []) or [])
        if len(buf) < n:
            buf = (buf + [0] * n)[:n]

        headPosition = int(buf[max(0, min(snakeSize - 1, n - 1))])
        foodDirection = int(state.get("foodDirection", 1) or 1)
        nextPosition = headPosition + foodDirection

        if nextPosition >= n:
            nextPosition = 0
        elif nextPosition < 0:
            nextPosition = n - 1

        # eat food
        if int(nextPosition) == int(state.get("foodPosition", -1)):
            snakeSize += 1
            if snakeSize <= n:
                # bodyColor = foodColor
                state["bodyColor"] = tuple(state.get("foodColor", (255, 255, 255)))
                rng = rng_load(state, seed=int(state.get("seed", 1)))
                self._spawn_food(state, rng=rng)
                self._determine_food_direction(state)
                state["interval_ms"] = int(1000 / (70 + snakeSize * 2))
                state["isFlashing"] = True
                rng_save(state, rng)
            else:
                state["shouldChangeColor"] = True
                snakeSize = 1
                state["snakeSize"] = snakeSize
                state["snakePositions"] = [0] * n
                self._restart_game(state, params=params)
                return

        # Arduino semantics:
        #   snakePositions[snakeSize] = nextPosition;  // NOTE: can go out of bounds in sketch
        #   for i=0..snakeSize-1: snakePositions[i] = snakePositions[i+1];
        # We clamp indices here to keep Python safe while preserving the look.
        write_idx = snakeSize
        if write_idx >= n:
            write_idx = n - 1
        buf[write_idx] = int(nextPosition)

        max_i = min(snakeSize, n - 1)
        for i in range(max_i):
            buf[i] = buf[i + 1]

        state["snakeSize"] = snakeSize
        state["snakePositions"] = buf

    def _check_collision(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        snakeSize = int(state.get("snakeSize", 1) or 1)
        buf = list(state.get("snakePositions", []) or [])
        if len(buf) < n:
            buf = (buf + [0] * n)[:n]
        head_idx = max(0, min(snakeSize - 1, n - 1))
        head = int(buf[head_idx])
        for i in range(max(0, min(snakeSize - 1, n))):
            if int(buf[i]) == head:
                state["gameOver"] = True
                break

    def _spawn_food(self, state: Dict[str, Any], *, rng) -> None:
        n = int(state.get("_n", 1) or 1)
        snakeSize = int(state.get("snakeSize", 1) or 1)
        buf = list(state.get("snakePositions", []) or [])
        if len(buf) < n:
            buf = (buf + [0] * n)[:n]
        snake = set(int(x) for x in buf[:max(1, min(snakeSize, n))])
        # random position not on snake (recursive in Arduino; loop here)
        for _ in range(1000):
            fp = int(rng.randrange(n))
            if fp not in snake:
                state["foodPosition"] = fp
                break
        else:
            state["foodPosition"] = 0

        # random food color excluding white
        while True:
            r = int(rng.randrange(256))
            g = int(rng.randrange(256))
            b = int(rng.randrange(256))
            if not (r == 255 and g == 255 and b == 255):
                state["foodColor"] = (r, g, b)
                return

    def _determine_food_direction(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        snakeSize = int(state.get("snakeSize", 1) or 1)
        buf = list(state.get("snakePositions", []) or [])
        if len(buf) < n:
            buf = (buf + [0] * n)[:n]
        headPosition = int(buf[max(0, min(snakeSize - 1, n - 1))])
        foodPosition = int(state.get("foodPosition", 0) or 0)

        if foodPosition > headPosition:
            if (foodPosition - headPosition) <= n // 2:
                state["foodDirection"] = 1
            else:
                state["foodDirection"] = -1
        else:
            if (headPosition - foodPosition) <= n // 2:
                state["foodDirection"] = -1
            else:
                state["foodDirection"] = 1

    def _set_initial_colors(self, state: Dict[str, Any], *, rng) -> None:
        # keep trying until body != head and both != food (Arduino also checks !=0??)
        food = tuple(state.get("foodColor", (0, 0, 0)))
        for _ in range(1000):
            body = self._rand_color_non_white(rng)
            head = self._rand_color_non_white(rng)
            if body != head and body != food and head != food:
                state["bodyColor"] = body
                state["headColor"] = head
                return
        state["bodyColor"] = (0, 255, 0)
        state["headColor"] = (255, 0, 0)

    def _restart_game(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        # Matches Arduino restartGame()
        rng = rng_load(state, seed=int(state.get("seed", 1)))
        self._spawn_food(state, rng=rng)
        self._determine_food_direction(state)
        snakeSize = int(state.get("snakeSize", 1) or 1)
        state["interval_ms"] = int(1000 / (70 + snakeSize * 2))

        if snakeSize >= int(state.get("_n", 1) or 1):
            state["shouldChangeColor"] = True
            snakeSize = 1
            state["snakeSize"] = snakeSize
            state["snakePositions"] = [0] * int(state.get("_n", 1) or 1)

        if bool(state.get("shouldChangeColor", False)):
            # Generate random body color excluding white
            state["bodyColor"] = self._rand_color_non_white(rng)
            # Generate random head color excluding white and not equal to body/food
            food = tuple(state.get("foodColor", (0, 0, 0)))
            for _ in range(1000):
                head = self._rand_color_non_white(rng)
                if head != tuple(state.get("bodyColor")) and head != food:
                    state["headColor"] = head
                    break
            state["shouldChangeColor"] = False

        state["gameOver"] = False
        state["isFlashing"] = False
        rng_save(state, rng)

    @staticmethod
    def _rand_color_non_white(rng):
        while True:
            r = int(rng.randrange(256))
            g = int(rng.randrange(256))
            b = int(rng.randrange(256))
            if not (r == 255 and g == 255 and b == 255):
                return (r, g, b)

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Snake (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter.")

def register_snake_game_ino():
    effect = SnakeGameINO()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=288, mw=0, mh=0, fixed_dt=1/60))
    defn = BehaviorDef(
        "snake_game_ino",
        title="Snake (INO Port)",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
