from __future__ import annotations
SHIPPED = True

import random
from typing import Dict, Any, List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save

RGB = Tuple[int,int,int]

USES = ["preview","arduino"]

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def _scale(c: RGB, s: float) -> RGB:
    s = _clamp01(s)
    return (int(c[0]*s)&255, int(c[1]*s)&255, int(c[2]*s)&255)

def _init_state(state: Dict[str, Any], n: int, seed: int):
    state.clear()
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["n"] = int(n)
    state["player_start"] = int(n//2)
    state["player"] = int(n//2)
    state["wave"] = 1
    state["active_enemies"] = []  # list of dicts: pos,speed,color,alive
    state["bullets"] = []         # list of dicts: pos,dir
    state["killed"] = 0
    state["high"] = 0
    state["mode"] = "play"        # play | gameover
    state["mode_t"] = 0.0         # time since mode start
    state["last_shot_t"] = 0.0
    state["wave_end_t"] = 0.0
    _start_new_wave(state, t=0.0)

def _enemy_color(rng: random.Random) -> RGB:
    palette = [
        (255,0,0),(0,255,0),(255,255,0),(255,0,255),(0,255,255),(255,165,0),(128,0,128)
    ]
    return palette[rng.randrange(len(palette))]

def _create_enemy(state: Dict[str, Any]):
    rng = rng_load(state, seed=int(state.get('seed', 1337)))
    n = int(state["n"])
    enemies: List[dict] = state["active_enemies"]
    # start alternating sides with spacing
    idx = len(enemies)
    side = 0 if (idx % 2 == 0) else (n-1)
    # add drift spacing
    side = int(max(0, min(n-1, side + (idx//2)* (20 + rng.randrange(15, 51)))))
    enemies.append({
        "pos": side,
        "speed": 1.0,
        "color": _enemy_color(rng),
        "alive": True,
    })
    rng_save(state, rng)

def _start_new_wave(state: Dict[str, Any], *, t: float):
    # based on sketch: waveNumber++, numEnemies = 2*waveNumber
    state["wave"] = int(state.get("wave", 0) or 0) + 1 if t > 0 else int(state.get("wave", 1) or 1)
    w = int(state["wave"])
    state["active_enemies"] = []
    for _ in range(max(1, 2*w)):
        _create_enemy(state)
        if len(state["active_enemies"]) >= max(1, int(state["n"])//6):
            break
    state["wave_end_t"] = float(t) + 2.0  # WAVE_END_TIMEOUT=2000ms
    # clear bullets
    state["bullets"] = []

def _enter_gameover(state: Dict[str, Any], *, t: float):
    state["mode"] = "gameover"
    state["mode_t"] = 0.0
    # update high score
    killed = int(state.get("killed", 0) or 0)
    high = int(state.get("high", 0) or 0)
    if killed > high:
        state["high"] = killed
    # keep snapshot
    state["gameover_killed"] = killed

def _reset_run(state: Dict[str, Any], *, t: float):
    # restart like sketch
    state["player"] = int(state["player_start"])
    state["killed"] = 0
    state["wave"] = 0
    state["mode"] = "play"
    state["mode_t"] = 0.0
    state["last_shot_t"] = float(t)
    _start_new_wave(state, t=t)

def _step_play(state: Dict[str, Any], *, dt: float, t: float):
    n = int(state["n"])
    player = int(state["player"])
    enemies: List[dict] = state["active_enemies"]
    bullets: List[dict] = state["bullets"]
    # wave timeout => new wave
    if float(t) >= float(state.get("wave_end_t", 0.0) or 0.0):
        _start_new_wave(state, t=t)

    # find closest alive enemy
    closest = None
    closest_dist = 10**9
    for e in enemies:
        if not e.get("alive", True): 
            continue
        d = abs(int(e["pos"]) - player)
        if d < closest_dist:
            closest_dist = d
            closest = e

    # auto-move player slightly toward closest, bounded
    MAX_PLAYER_MOVE_DISTANCE = 35
    start = int(state["player_start"])
    if closest is not None:
        if closest_dist <= MAX_PLAYER_MOVE_DISTANCE:
            if int(closest["pos"]) < player:
                if player < (n-1-MAX_PLAYER_MOVE_DISTANCE):
                    player += 1
            else:
                if player > MAX_PLAYER_MOVE_DISTANCE:
                    player -= 1
        else:
            if player < start: player += 1
            elif player > start: player -= 1

    # enemy update: chase player
    for e in enemies:
        if not e.get("alive", True): 
            continue
        pos = int(e["pos"])
        direction = 1 if player > pos else -1
        pos += int(max(1, round(float(e.get("speed", 1.0)))))*direction
        if pos < 0: pos = 0
        if pos > n-1: pos = n-1
        e["pos"] = pos

    # collision: enemy touches player (within 1)
    touched = False
    for e in enemies:
        if not e.get("alive", True): 
            continue
        if abs(int(e["pos"]) - player) <= 1:
            touched = True
            break
    if touched:
        state["player"] = player
        _enter_gameover(state, t=t)
        return

    # shooting logic: every 0.5s attempt shoot toward closest if bullet slots available
    bullet_interval = 0.5
    if closest is not None and (float(t) - float(state.get("last_shot_t", 0.0) or 0.0)) >= bullet_interval:
        if len(bullets) < 3:
            direction = -1 if int(closest["pos"]) < player else 1
            bullets.append({"pos": player, "dir": direction})
        state["last_shot_t"] = float(t)

    # bullets update
    BULLET_SPEED = 2
    new_bullets = []
    for b in bullets:
        pos = int(b["pos"]) + int(b["dir"])*BULLET_SPEED
        if pos < 0 or pos >= n:
            continue
        b["pos"] = pos
        new_bullets.append(b)
    bullets = new_bullets

    # bullet-enemy collision (within 1)
    killed = int(state.get("killed", 0) or 0)
    for b in list(bullets):
        hit = None
        for e in enemies:
            if not e.get("alive", True): 
                continue
            if abs(int(e["pos"]) - int(b["pos"])) <= 1:
                hit = e
                break
        if hit is not None:
            hit["alive"] = False
            killed += 1
            try:
                bullets.remove(b)
            except Exception:
                pass

    state["killed"] = killed
    state["player"] = player
    state["bullets"] = bullets

def _render_play(n: int, state: Dict[str, Any]) -> List[RGB]:
    out = [(0,0,0) for _ in range(n)]
    player = int(state.get("player", n//2))
    # player: blue cross-ish + red center dim like sketch (mapped)
    def setp(i: int, c: RGB):
        if 0 <= i < n:
            out[i] = c
    # blue parts
    blue = (0,0,255)
    setp(player-2, blue); setp(player-1, blue); setp(player+1, blue); setp(player+2, blue)
    # red-ish center (dim)
    setp(player, (77//2,0,0))

    # enemies: two-pixel wide
    for e in state.get("active_enemies", []):
        if not e.get("alive", True):
            continue
        pos = int(e.get("pos", 0))
        col = tuple(e.get("color", (255,255,255)))
        if 0 <= pos < n:
            out[pos] = col
        if 0 <= pos-1 < n:
            out[pos-1] = col

    # bullets: yellow
    for b in state.get("bullets", []):
        p = int(b.get("pos", -1))
        if 0 <= p < n:
            out[p] = (255,255,0)
    return out

def _render_gameover(n: int, state: Dict[str, Any]) -> List[RGB]:
    # Approximate sketch: red dim wash + black "knight rider" dot, show high score in blue at start.
    t = float(state.get("mode_t", 0.0) or 0.0)
    killed = int(state.get("gameover_killed", state.get("killed", 0)) or 0)
    high = int(state.get("high", 0) or 0)

    out = [(30,0,0) for _ in range(n)]  # dim red
    # show killed count as green markers at start region (first 'killed' pixels)
    for i in range(min(killed, n)):
        out[i] = (0,255,0)

    # first 2 seconds: show high score in blue overlay
    if t >= 2.0 and high > 0:
        for i in range(min(high, n)):
            out[i] = (0,0,255)

    # knight rider black dot
    dur = 2.0  # seconds
    phase = (t % dur) / dur
    # bounce
    x = phase*2.0
    if x <= 1.0:
        pos = int(round(x*(n-1)))
    else:
        pos = int(round((2.0-x)*(n-1)))
    if 0 <= pos < n:
        out[pos] = (0,0,0)
    return out

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None) -> List[RGB]:
    n = max(1, int(num_leds))
    if state is None or not isinstance(state, dict) or state.get("n") != n:
        # seed stable per layer
        seed = int(params.get("_seed", 1337) or 1337)
        state = {} if not isinstance(state, dict) else state
        _init_state(state, n, seed)

    mode = str(state.get("mode", "play"))
    if mode == "gameover":
        return _render_gameover(n, state)
    return _render_play(n, state)

def _update(*, state: dict, params: dict, dt: float, t: float, audio=None):
    n = max(1, int(params.get("_num_leds", state.get("n", 1)) or state.get("n", 1)))
    if state is None or not isinstance(state, dict) or state.get("n") != n:
        seed = int(params.get("_seed", 1337) or 1337)
        state.clear()
        _init_state(state, n, seed)

    # advance mode timer
    state["mode_t"] = float(state.get("mode_t", 0.0) or 0.0) + float(dt or 0.0)

    mode = str(state.get("mode", "play"))
    if mode == "play":
        _step_play(state, dt=float(dt or 0.0), t=float(t))
        return

    # gameover: run for ~4s then restart
    if float(state.get("mode_t", 0.0) or 0.0) >= 4.0:
        _reset_run(state, t=float(t))

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Asteroids (Game) is preview-ready but Arduino export is not wired yet.")

def register_asteroids_game():
    bd = BehaviorDef(
        "asteroids_game",
        title="Asteroids (Game)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    bd.stateful = True
    bd.update = _update
    return register(bd)
