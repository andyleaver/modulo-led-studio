from __future__ import annotations
SHIPPED = True

import random
from typing import Dict, Any, List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save

USES = ["preview", "arduino"]


def _rand(rng: random.Random, n: int) -> int:
    return rng.randrange(n) if n > 0 else 0


def _init_state(state: Dict[str, Any], num_leds: int, seed: int, params: Dict[str, Any]):
    state.clear()
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["num_leds"] = int(num_leds)

    # Ball
    state["ball_size"] = int(params.get("ball_size", 1))
    rng = rng_load(state, seed=seed)
    state["ball_pos"] = _rand(rng, int(num_leds))
    state["ball_dir"] = -1 if (_rand(rng, 2) == 0) else 1

    # Blocks
    state["num_blocks"] = int(params.get("num_blocks", 20))
    state["max_block_health"] = int(params.get("max_block_health", 5))
    # health mapping by "color index" (1..3)
    state["block_health_by_color"] = [0, 2, 4, 5]

    nb = state["num_blocks"]
    state["block_pos"] = [0] * nb
    state["block_health"] = [0] * nb
    state["block_color"] = [0] * nb  # 1..3

    _respawn_blocks(state)
    # Deterministic timing accumulator for fixed-tick update.
    state["_acc"] = 0.0
    state["_flash_ticks"] = 0
    rng_save(state, rng)



def _init_state_matrix(state: Dict[str, Any], mw: int, mh: int, seed: int, params: Dict[str, Any]):
    # Matrix-mode breakout: 2D ball + brick grid.
    state.clear()
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["mw"] = int(mw)
    state["mh"] = int(mh)
    rng = rng_load(state, seed=seed)

    top_gap = int(params.get("top_gap_rows", 4) or 4)
    brick_rows = int(params.get("brick_rows", 2) or 2)
    top_gap = max(0, min(top_gap, max(0, mh - 2)))
    brick_rows = max(1, min(brick_rows, max(1, mh - top_gap - 2)))

    state["top_gap_rows"] = top_gap
    state["brick_rows"] = brick_rows

    # Bricks occupy rows [top_gap, top_gap+brick_rows-1], columns 1..mw-2
    max_h = int(params.get("max_block_health", 3) or 3)
    max_h = max(1, min(max_h, 9))
    state["max_block_health"] = max_h

    bricks = {}
    for y in range(top_gap, top_gap + brick_rows):
        for x in range(1, mw - 1):
            # Health gradient: top row stronger
            base = max_h
            if brick_rows > 1:
                # Map row within brick band to health range
                rel = y - top_gap
                base = max(1, max_h - rel)
            bricks[(x, y)] = base
    state["bricks"] = bricks

    # Ball starts in the empty gap region, inside walls
    if top_gap <= 0:
        sy = mh // 2
    else:
        sy = _rand(rng, top_gap)
    sx = 1 + _rand(rng, max(1, (mw - 2)))
    state["ball_x"] = int(sx)
    state["ball_y"] = int(max(1, min(mh - 2, sy)))

    # Random initial velocity: dx +/-1, dy +/-1 but bias downward
    state["ball_dx"] = -1 if (_rand(rng, 2) == 0) else 1
    state["ball_dy"] = 1  # start moving down into bricks/world

    state["_acc"] = 0.0
    state["_flash_ticks"] = 0
    state["ball_free_ticks"] = 0
    state["ball_free"] = False
    state["free_jitter_acc"] = 0
    state["free_nohit"] = 0


def _all_bricks_destroyed_matrix(state: Dict[str, Any]) -> bool:
    b = state.get("bricks") or {}
    return all(int(v) <= 0 for v in b.values())


def _step_matrix(state: Dict[str, Any], params: Dict[str, Any]):
    mw = int(state.get("mw", 0) or 0)
    mh = int(state.get("mh", 0) or 0)
    if mw <= 1 or mh <= 1:
        return

    x = int(state.get("ball_x", 1) or 1)
    y = int(state.get("ball_y", 1) or 1)
    dx = int(state.get("ball_dx", 1) or 1)
    dy = int(state.get("ball_dy", 1) or 1)
    dx = -1 if dx < 0 else 1
    dy = -1 if dy < 0 else 1

    # LOOP BREAKER (pre-clear only): detect repeating states while bricks remain and nudge.
    try:
        bricks = state.get('bricks') or {}
        bricks_left = any(int(h) > 0 for h in bricks.values())
        if bricks_left and int(state.get('ball_free_ticks', 0) or 0) <= 0:
            hist = state.get('loop_hist')
            if not isinstance(hist, list):
                hist = []
            st = (int(x), int(y), int(dx), int(dy))
            if st in hist:
                state['loop_repeat'] = int(state.get('loop_repeat', 0) or 0) + 1
            else:
                state['loop_repeat'] = 0
            hist.append(st)
            if len(hist) > 60:
                hist = hist[-60:]
            state['loop_hist'] = hist

            # Only nudge occasionally (keep motion natural)
            if int(state.get('loop_repeat', 0) or 0) >= 6:
                state['loop_repeat'] = 0
                rng = rng_load(state, seed=int(state.get('seed', 1) or 1))
                if _rand(rng, 2) == 0:
                    dx *= -1
                else:
                    dy *= -1
    except Exception:
        pass

    # ANTI-LOOP JITTER:
    # When the ball is in the post-clear 'free' window, small periodic direction nudges
    # prevent it getting stuck in a perfect cycle that never reaches invaders.
    if int(state.get("ball_free_ticks", 0) or 0) > 0:
        try:
            state["free_jitter_acc"] = int(state.get("free_jitter_acc", 0) or 0) + 1
            period = int(params.get("free_jitter_period", 18) or 18)
            period = max(6, min(period, 120))
            if state["free_jitter_acc"] >= period:
                state["free_jitter_acc"] = 0
                rng = rng_load(state, seed=int(state.get("seed", 1) or 1))
                # with some probability, flip dx or dy
                p = float(params.get("free_jitter_prob", 0.35) or 0.35)
                r = (_rand(rng, 1000) / 1000.0)
                if r < p:
                    if _rand(rng, 2) == 0:
                        dx *= -1
                    else:
                        dy *= -1
        except Exception:
            pass

    nx = x + dx
    ny = y + dy

    # Bounce off walls (no wrap)
    if nx <= 0 or nx >= mw - 1:
        dx *= -1
        nx = x + dx
    if ny <= 0 or ny >= mh - 1:
        dy *= -1
        ny = y + dy


    hit_brick = False
    # Brick collision (robust): check diagonal + axis cells so we don't miss side-hits.
    bricks = state.get("bricks") or {}

    def _hit_at(hx: int, hy: int) -> bool:
        try:
            if (hx, hy) in bricks and int(bricks[(hx, hy)]) > 0:
                bricks[(hx, hy)] = int(bricks[(hx, hy)]) - 1
                return True
        except Exception:
            pass
        return False

    # Try diagonal first
    if _hit_at(nx, ny):
        hit_brick = True
        dy *= -1
        ny = y + dy
    else:
        # Side hit on x?
        if _hit_at(nx, y):
            hit_brick = True
            dx *= -1
            nx = x + dx
        # Side hit on y?
        if _hit_at(x, ny):
            hit_brick = True
            dy *= -1
            ny = y + dy

    if hit_brick:
        state["bricks"] = bricks



    state["ball_x"] = int(max(1, min(mw - 2, nx)))
    state["ball_y"] = int(max(1, min(mh - 2, ny)))
    state["ball_dx"] = int(dx)
    state["ball_dy"] = int(dy)

    # ARM FREE WINDOW WHEN BRICKS CLEARED (matrix mode)
    try:
        if int(state.get("ball_free_ticks", 0) or 0) <= 0:
            bricks = state.get("bricks") or {}
            if (len(bricks) > 0) and (not any(int(h) > 0 for h in bricks.values())):
                state["ball_free_ticks"] = int(params.get("ball_free_ticks", 180) or 180)
                state["ball_free"] = True
                state["ball_free"] = True
    except Exception:
        pass



def _get_hit_targets_matrix(*, state: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Expose remaining bricks as hittable targets (for other layers).
    targets: List[Dict[str, Any]] = []
    bricks = state.get("bricks") or {}
    for (x, y), h in bricks.items():
        try:
            if int(h) > 0:
                targets.append({"kind": "brick", "entity_id": f"{int(x)}:{int(y)}", "x": int(x), "y": int(y)})
        except Exception:
            pass
    return targets


def _apply_hit_matrix(*, state: Dict[str, Any], params: Dict[str, Any], hit: Dict[str, Any], target: Dict[str, Any]) -> bool:
    # Allow bullets to damage bricks ONLY after invaders are gone (signaled by hit["invaders_cleared"]=True)
    try:
        if not bool(hit.get("invaders_cleared", False)):
            return False
        if str(target.get("kind", "")) != "brick":
            return False
        if str(hit.get("kind", "")) != "bullet":
            return False
        x = int(target.get("x", -1)); y = int(target.get("y", -1))
        bricks = state.get("bricks") or {}
        k = (x, y)
        if k in bricks and int(bricks[k]) > 0:
            bricks[k] = int(bricks[k]) - 1
            state["bricks"] = bricks
            return True
    except Exception:
        pass
    return False


def _render_matrix(state: Dict[str, Any], params: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    mw = int(state.get("mw", 0) or 0)
    mh = int(state.get("mh", 0) or 0)
    n = mw * mh
    out = [(0, 0, 0)] * n

    max_h = int(state.get("max_block_health", 3) or 3)
    bricks = state.get("bricks") or {}
    for (x, y), h in bricks.items():
        h = int(h)
        if h <= 0:
            continue
        inten = int((h - 1) * 255 / max(1, (max_h - 1))) if max_h > 1 else 255
        # Use warm brick colors by health
        if h >= 3:
            col = (inten, 0, 0)
        elif h == 2:
            col = (inten, int(inten * 0.5), 0)
        else:
            col = (inten, inten, 0)
        idx = int(y) * mw + int(x)
        if 0 <= idx < n:
            out[idx] = col

    bx = int(state.get("ball_x", 1) or 1)
    by = int(state.get("ball_y", 1) or 1)
    bi = by * mw + bx
    if 0 <= bi < n:
        out[bi] = (255, 255, 255)

    return out


def _respawn_blocks(state: Dict[str, Any]):
    rng = rng_load(state, seed=int(state.get('seed', 1)))
    num_leds = int(state["num_leds"])
    nb = int(state["num_blocks"])
    bh = state["block_health_by_color"]

    for i in range(nb):
        state["block_pos"][i] = _rand(rng, num_leds)
        color_idx = rng.randrange(1, 4)  # 1..3
        state["block_health"][i] = int(bh[color_idx])
        state["block_color"][i] = int(color_idx)

    state["all_destroyed"] = False
    rng_save(state, rng)


def _all_blocks_destroyed(state: Dict[str, Any]) -> bool:
    for h in state["block_health"]:
        if h > 0:
            return False
    return True


def _step_one(state: Dict[str, Any]):
    num_leds = int(state["num_leds"])
    ball_size = int(state["ball_size"])
    ball_pos = int(state["ball_pos"])
    ball_dir = int(state["ball_dir"])

    next_pos = ball_pos + ball_dir

    # wall collision (same as sketch: bounce when next <=0 or >= NUM- ballSize)
    if next_pos <= 0 or next_pos >= (num_leds - ball_size):
        state["ball_dir"] = -ball_dir
        return  # exit early to avoid skipping collisions

    # block collision
    nb = int(state["num_blocks"])
    collided = False
    for i in range(nb):
        if state["block_health"][i] <= 0:
            continue
        bp = int(state["block_pos"][i])
        if next_pos >= bp and next_pos < (bp + ball_size):
            state["block_health"][i] -= 1
            # if becomes 0, "disappear" - sketch uses continue
            state["ball_dir"] = -ball_dir
            collided = True
            break

    if not collided:
        state["ball_pos"] = next_pos


def _tick(state: Dict[str, Any], params: Dict[str, Any]):
    # speed steps per tick (like sketch uses loop for steps < ballSpeed)
    speed = int(params.get("ball_speed", 1))
    if speed < 1:
        speed = 1
    for _ in range(speed):
        _step_one(state)


def _render(state: Dict[str, Any], params: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    num_leds = int(state["num_leds"])
    ball_pos = int(state["ball_pos"])
    ball_size = int(state["ball_size"])

    out = [(0, 0, 0)] * num_leds

    # If all destroyed: render a one-tick blue flash.
    # Respawn is handled in the fixed-tick update to keep render side-effect free.
    if int(state.get('_flash_ticks', 0) or 0) > 0:
        for i in range(num_leds):
            out[i] = (0, 0, 255)
        return out

    # draw blocks as single pixels with intensity by health
    max_h = int(state["max_block_health"])
    nb = int(state["num_blocks"])
    for j in range(nb):
        h = int(state["block_health"][j])
        if h <= 0:
            continue
        pos = int(state["block_pos"][j])
        if 0 <= pos < num_leds:
            # intensity mapping 1..max -> 0..255 (like Arduino map)
            inten = int((h - 1) * 255 / max(1, (max_h - 1))) if max_h > 1 else 255
            c = int(state["block_color"][j])
            # NOTE: original sketch comments are inconsistent; we keep its channel mapping behavior.
            r = 0
            g = 0
            b = 0
            if c == 1:
                g = inten
            elif c == 2:
                b = inten
            else:
                g = inten
            out[pos] = (r, g, b)

    # draw ball (red) over blocks
    for i in range(ball_pos, min(num_leds, ball_pos + ball_size)):
        if 0 <= i < num_leds:
            out[i] = (255, 0, 0)

    return out


def _preview_emit(*, num_leds: int, params: dict, t: float, state=None):
    if state is None:
        state = {}
    params = params or {}
    seed = int(params.get("seed", 1))
    mw = int(params.get('_mw', 0) or 0)
    mh = int(params.get('_mh', 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(num_leds):
        if int(state.get('mw', -1)) != mw or int(state.get('mh', -1)) != mh or int(state.get('seed', -1)) != (seed & 0xFFFFFFFF) or 'ball_x' not in state:
            _init_state_matrix(state, mw, mh, seed, params)
        return _render_matrix(state, params)

    if state.get("num_leds") != int(num_leds) or "ball_pos" not in state or int(state.get("seed", -1)) != (seed & 0xFFFFFFFF):
        _init_state(state, int(num_leds), seed, params)
    return _render(state, params)


def _update(*, state: Dict[str, Any], params: Dict[str, Any], dt: float, t: float, audio=None):
    """Fixed-tick update driven by PreviewEngine's SimClock."""
    params = params or {}
    seed = int(params.get('seed', 1))
    n = int(params.get('_num_leds', state.get('num_leds', 60) or 60))

    mw = int(params.get('_mw', 0) or 0)
    mh = int(params.get('_mh', 0) or 0)
    if mw > 1 and mh > 1 and mw * mh == int(n):
        if int(state.get('mw', -1)) != mw or int(state.get('mh', -1)) != mh or int(state.get('seed', -1)) != (seed & 0xFFFFFFFF) or 'ball_x' not in state:
            _init_state_matrix(state, mw, mh, seed, params)
        # Fixed tick update
        acc = float(state.get('_acc', 0.0) or 0.0) + float(dt)
        mps = float(params.get('moves_per_second', 30.0) or 30.0)
        mps = max(1.0, min(mps, 240.0))
        step_dt = 1.0 / mps
        steps = 0
        while acc >= step_dt:
            acc -= step_dt
            steps += 1
            # Flash tick decay / respawn behavior
            ft = int(state.get('_flash_ticks', 0) or 0)
            if ft > 0:
                state['_flash_ticks'] = max(0, ft - 1)
            else:
                _step_matrix(state, params)
                if _all_bricks_destroyed_matrix(state):
                    state['_flash_ticks'] = 1
                    try:
                        bft = int(state.get('ball_free_ticks', 0) or 0)
                        if bft <= 0:
                            state['ball_free_ticks'] = int(params.get('ball_free_ticks', 180) or 180)
                    except Exception:
                        state['ball_free_ticks'] = 180
        state['_acc'] = float(acc)
        # Decrement free window by steps
        try:
            bft = int(state.get('ball_free_ticks', 0) or 0)
            if bft > 0:
                state['ball_free_ticks'] = max(0, bft - int(steps))
        except Exception:
            pass
        return

    if int(state.get('num_leds', -1)) != int(n) or 'ball_pos' not in state or int(state.get('seed', -1)) != (seed & 0xFFFFFFFF):
        _init_state(state, int(n), seed, params)

    # If we flashed "all destroyed" last tick, respawn now.
    ft = int(state.get('_flash_ticks', 0) or 0)
    if ft > 0:
        state['_flash_ticks'] = ft - 1
        if ft - 1 <= 0:
            _respawn_blocks(state)
        return

    # Rate control: update at moves_per_second, but keep deterministic by accumulating fixed dt.
    mps = float(params.get('moves_per_second', 30.0))
    if mps <= 1.0:
        mps = 1.0
    acc = float(state.get('_acc', 0.0) or 0.0)
    acc += float(dt)
    step_dt = 1.0 / mps
    steps = 0
    while acc >= step_dt and steps < 10:
        _tick(state, params)
        acc -= step_dt
        steps += 1
    state['_acc'] = float(acc)

    # Detect all blocks destroyed and schedule a one-tick blue flash.
    if 'blocks' in state and _all_blocks_destroyed(state):
        # (strip mode) engine-level flash handles showcases; keep internal flash disabled.
        state['_flash_ticks'] = 0
        # Cross-layer interaction window: ball can interact with other layers for a short time.
        try:
            bft = int(state.get('ball_free_ticks', 0) or 0)
            if bft <= 0:
                state['ball_free_ticks'] = int(params.get('ball_free_ticks', 180) or 180)
        except Exception:
            state['ball_free_ticks'] = 180



def _get_hit_events(*, state: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit hit events for cross-layer interactions (Breakout ball).

    Active only when ball_free_ticks > 0.
    In matrix mode, uses ball_x/ball_y. In strip mode, uses ball_pos index.
    """
    try:
        if (not bool(state.get("ball_free", False))) and int(state.get("ball_free_ticks", 0) or 0) <= 0:
            return []
        # Matrix mode
        if "ball_x" in state and "ball_y" in state:
            x = int(state.get("ball_x", 0) or 0)
            y = int(state.get("ball_y", 0) or 0)
            return [{"kind": "ball", "x": x, "y": y, "damage": 1}]
        # Strip mode
        bp = state.get("ball_pos")
        if bp is None:
            return []
        mw = int(params.get("_mw", 0) or 0)
        if mw > 1:
            x = int(int(bp) % mw)
            y = int(int(bp) // mw)
        else:
            x = int(bp); y = 0
        return [{"kind": "ball", "x": x, "y": y, "damage": 1}]
    except Exception:
        return []
        bp = state.get('ball_pos')
        if bp is None and 'ball_x' in state and 'ball_y' in state:
            bp = (int(state.get('ball_x', 0) or 0), int(state.get('ball_y', 0) or 0))
        if not (isinstance(bp, (list, tuple)) and len(bp) >= 2):
            return []
        if isinstance(bp, (list, tuple)) and len(bp) >= 2:
            x = int(bp[0]); y = int(bp[1])
        else:
            # strip mode: convert linear index to x,y using mw if available
            mw = int(params.get('_mw', 0) or 0)
            if mw > 1:
                x = int(int(bp) % mw)
                y = int(int(bp) // mw)
            else:
                x = int(bp); y = 0
        return [{
            "kind": "ball",
            "x": x,
            "y": y,
            "damage": 1,
        }]
    except Exception:
        return []

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Breakout (Game) is preview-ready but Arduino export is not wired yet.")


def register_breakout_game():
    defn = BehaviorDef(
        "breakout_game",
        title="Breakout (Game)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = _update
    defn.get_hit_events = _get_hit_events
    # Optional: bricks can be hit by other layers (e.g., bullets) in matrix mode
    defn.get_hit_targets = _get_hit_targets_matrix
    defn.apply_hit = _apply_hit_matrix
    register(defn)