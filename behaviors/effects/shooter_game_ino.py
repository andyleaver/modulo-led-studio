from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save
from behaviors.stateful_adapter import StatefulEffect, AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]
USES = ["preview", "arduino"]

# === Faithful port of Shooter sketch (3rd section) from 'game visuals.ino' ===
NUM_PIXELS_DEFAULT = 288

ENEMY_SPEED = 1
PLAYER_BRIGHTNESS_BLUE = 255
PLAYER_BRIGHTNESS_RED = 77
ENEMY_BRIGHTNESS = 100
BULLET_COLOR = (255, 255, 0)  # 0xFFFF00
BULLET_BRIGHTNESS = 100
BULLET_SPEED = 2
MAX_PLAYER_MOVE_DISTANCE = 35
ENEMY_WAVE_SPACING = 20
FRAME_DELAY_MS = 10
MAX_BULLETS = 3
GAME_OVER_ANIMATION_DURATION_MS = 2000
WAVE_END_TIMEOUT_MS = 2000

PALETTE_U32 = [0xFF0000, 0x00FF00, 0xFFFF00, 0xFF00FF, 0x00FFFF, 0xFFA500, 0x800080, 0xFFFFFF]

def _u32_to_rgb(c: int) -> RGB:
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)

def _scale_rgb(c: RGB, brightness_0_255: int) -> RGB:
    b = 0 if brightness_0_255 < 0 else (255 if brightness_0_255 > 255 else int(brightness_0_255))
    return (int(c[0] * b / 255) & 255, int(c[1] * b / 255) & 255, int(c[2] * b / 255) & 255)

class ShooterGameINO(StatefulEffect):
    """Mechanical translation of the Arduino logic and ordering (including quirks)."""

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", NUM_PIXELS_DEFAULT) or NUM_PIXELS_DEFAULT)
        seed = int(params.get("seed", 1)) & 0xFFFFFFFF
        state.clear()
        state["_n"] = n
        state["seed"] = seed

        # Mirrors globals
        state["highestScore"] = 0
        state["playerStartPosition"] = n // 2
        state["playerPosition"] = n // 2

        state["bulletPositions"] = [state["playerPosition"]] * MAX_BULLETS
        state["bulletDirections"] = [0] * MAX_BULLETS
        state["isBulletActive"] = [False] * MAX_BULLETS
        state["isShootingLeft"] = False
        state["isShootingRight"] = False

        # NOTE: closestEnemy* is computed in drawEnemies() at END of frame, and used next frame.
        state["closestEnemyPosition"] = -1
        state["closestEnemyIndex"] = -1

        state["activeEnemyCount"] = 0
        state["waveNumber"] = 1
        state["waveEndTime_ms"] = 0
        state["enemiesKilled"] = 0

        state["bulletFireInterval_ms"] = 500
        state["lastShotTime_ms"] = 0

        # Shooter sketch has separate static lastBulletIndex in shootLeft and shootRight
        state["_lastBulletIndexLeft"] = 0
        state["_lastBulletIndexRight"] = 0

        # enemyWaves: fixed-size array in Arduino (NUM_PIXELS/6). We keep a list of dicts.
        state["enemyWaves"] = []  # we allow sparse/holes; activeEnemyCount controls iteration

        # Game over animation state machine (non-blocking emulation)
        state["_gameover_active"] = False
        state["_gameover_start_ms"] = 0
        state["_knight_pos"] = 0
        state["_knight_dir"] = 1
        state["_show_highscore"] = False
        state["_show_highscore_start_ms"] = 0

        # Virtual millis counter (Arduino uses delay(FRAME_DELAY))
        state["_millis"] = 0
        state["_acc_ms"] = 0.0

        rng = rng_load(state, seed=seed)
        # The original sketch does NOT call startNewWave in setup; it relies on waveEndTime default 0 so it starts immediately.
        # We'll match by leaving waveEndTime at 0; the first frame will startNewWave().
        rng_save(state, rng)

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        # Fixed-step loop using FRAME_DELAY_MS. Use our virtual millis to mirror Arduino.
        acc = float(state.get("_acc_ms", 0.0) or 0.0) + float(dt) * 1000.0
        steps = 0
        while acc >= FRAME_DELAY_MS and steps < 50:
            acc -= FRAME_DELAY_MS
            state["_millis"] = int(state.get("_millis", 0) or 0) + FRAME_DELAY_MS
            self._loop_once(state)
            steps += 1
        state["_acc_ms"] = acc

        # If dt is tiny (e.g. paused), still advance animations based on virtual millis already.

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        px: List[RGB] = [(0, 0, 0)] * n

        # Emulate gameOverAnimation visuals when active
        if bool(state.get("_gameover_active", False)):
            killed = int(state.get("enemiesKilled", 0) or 0)
            # Red background
            for i in range(n):
                px[i] = (30, 0, 0)
            # show killed as green up to killed
            for i in range(min(n, killed)):
                px[i] = (0, 255, 0)
            kp = int(state.get("_knight_pos", 0) or 0)
            if 0 <= kp < n:
                px[kp] = (0, 0, 0)
            return px

        if bool(state.get("_show_highscore", False)):
            hs = int(state.get("highestScore", 0) or 0)
            for i in range(min(n, hs)):
                px[i] = (0, 0, 255)
            return px

        # Normal frame is drawn in this order in Arduino:
        # clear -> drawPlayer -> drawEnemies -> draw bullets
        self._draw_player(px, state)
        self._draw_enemies(px, state)
        self._draw_bullets(px, state)
        return px

    # ===== Arduino loop (one iteration) =====

    def _loop_once(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        now_ms = int(state.get("_millis", 0) or 0)

        # wave control
        if now_ms >= int(state.get("waveEndTime_ms", 0) or 0):
            self._start_new_wave(state, now_ms)

        # updatePlayerPosition uses closestEnemyPosition from previous frame and checks touches vs enemies.
        self._update_player_position(state)

        # During game over animation, restartGame is called immediately after animation in Arduino.
        # Our state machine triggers restart when animation completes.
        if bool(state.get("_gameover_active", False)) or bool(state.get("_show_highscore", False)):
            self._anim_step(state)
            return

        self._update_bullets(state)

        # Shooting decision uses closestEnemyPosition (computed in drawEnemies at END of prior frame)
        lastShot = int(state.get("lastShotTime_ms", 0) or 0)
        if now_ms - lastShot >= int(state.get("bulletFireInterval_ms", 500) or 500):
            if (not bool(state["isBulletActive"][0])) and int(state.get("activeEnemyCount", 0) or 0) > 0:
                ce = int(state.get("closestEnemyPosition", -1) or -1)
                pp = int(state.get("playerPosition", n // 2) or n // 2)
                if ce != -1:
                    if ce < pp:
                        self._shoot_left(state)
                    else:
                        self._shoot_right(state)
            state["lastShotTime_ms"] = now_ms

        # updateEnemyWave for each alive (up to activeEnemyCount)
        waves = list(state.get("enemyWaves", []) or [])
        active = int(state.get("activeEnemyCount", 0) or 0)
        for i in range(active):
            if i >= len(waves):
                break
            w = waves[i]
            if bool(w.get("isAlive", False)):
                self._update_enemy_wave(state, w)
        state["enemyWaves"] = waves

        # Then clear, drawPlayer, drawEnemies, drawBullets happens in render(), but drawEnemies contains logic:
        # it recomputes closestEnemyPosition for NEXT frame and processes bullet collisions.
        # We must run that logic here each loop to update state consistently with Arduino.
        self._draw_enemies_logic_only(state)

    # ===== Ported functions =====

    def _start_new_wave(self, state: Dict[str, Any], now_ms: int) -> None:
        state["activeEnemyCount"] = 0
        state["waveNumber"] = int(state.get("waveNumber", 1) or 1) + 1
        waveNumber = int(state["waveNumber"])
        numEnemies = 2 * waveNumber

        # Do NOT clear enemyWaves in Arduino (but activeEnemyCount gates everything).
        # We'll keep list and overwrite at indexes 0..activeEnemyCount-1.
        rng = rng_load(state, seed=int(state.get("seed", 1)))
        for _ in range(numEnemies):
            self._create_enemy_wave(state, rng)
        rng_save(state, rng)

        state["waveEndTime_ms"] = int(now_ms + WAVE_END_TIMEOUT_MS)

    def _create_enemy_wave(self, state: Dict[str, Any], rng) -> None:
        n = int(state.get("_n", 1) or 1)
        waves = list(state.get("enemyWaves", []) or [])
        active = int(state.get("activeEnemyCount", 0) or 0)
        pp = int(state.get("playerPosition", n // 2) or n // 2)

        # Quirk: condition reads enemyWaves[active-1].position even when active==0.
        last_pos = 0
        if len(waves) >= 1:
            last_pos = int(waves[-1].get("position", 0) or 0) if active == 0 else int(waves[min(active - 1, len(waves) - 1)].get("position", 0) or 0)

        if active >= (n // 6) or abs(pp - last_pos) <= ENEMY_WAVE_SPACING * 2:
            return

        direction = 1 if int(rng.randrange(2)) == 0 else -1
        colorChoice = int(rng.randrange(7))
        color_u32 = int(PALETTE_U32[colorChoice]) if 0 <= colorChoice < 7 else 0xFFFFFF

        startingSide = 0 if (active % 2 == 0) else (n - 1)
        startingSide += (active // 2) * (ENEMY_WAVE_SPACING + int(rng.randrange(15, 51)))

        # In Arduino this may exceed bounds; NeoPixel setPixelColor ignores out-of-range in our preview, but keep in-range for state.
        if startingSide < 0:
            startingSide = 0
        if startingSide > n - 1:
            startingSide = n - 1

        wave = {
            "position": int(startingSide),
            "direction": int(direction),
            "speed": int(ENEMY_SPEED),
            "color": int(color_u32),
            "brightness": int(ENEMY_BRIGHTNESS),
            "isAlive": True,
        }

        # Ensure list big enough and assign at index 'active'
        if len(waves) <= active:
            waves.extend([{"position": 0, "direction": 1, "speed": ENEMY_SPEED, "color": 0xFFFFFF, "brightness": ENEMY_BRIGHTNESS, "isAlive": False}
                          for _ in range(active - len(waves) + 1)])
        waves[active] = wave
        state["enemyWaves"] = waves
        state["activeEnemyCount"] = active + 1

    def _update_enemy_wave(self, state: Dict[str, Any], wave: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        pp = int(state.get("playerPosition", n // 2) or n // 2)
        pos = int(wave.get("position", 0) or 0)
        speed = int(wave.get("speed", ENEMY_SPEED) or ENEMY_SPEED)
        directionToPlayer = 1 if pp > pos else -1
        pos += directionToPlayer * speed
        if pos <= 0 or pos >= n - 1:
            wave["direction"] = int(wave.get("direction", 1) or 1) * -1
        wave["position"] = int(pos)

    def _update_bullets(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        for bi in range(MAX_BULLETS):
            if bool(state["isBulletActive"][bi]):
                state["bulletPositions"][bi] = int(state["bulletPositions"][bi]) + int(state["bulletDirections"][bi]) * BULLET_SPEED
                if state["bulletPositions"][bi] < 0 or state["bulletPositions"][bi] >= n:
                    state["isBulletActive"][bi] = False

    def _shoot_left(self, state: Dict[str, Any]) -> None:
        last = int(state.get("_lastBulletIndexLeft", 0) or 0)
        bulletIndex = last
        for _ in range(MAX_BULLETS):
            bulletIndex = (bulletIndex + 1) % MAX_BULLETS
            if not bool(state["isBulletActive"][bulletIndex]):
                state["isBulletActive"][bulletIndex] = True
                state["isShootingLeft"] = True
                state["isShootingRight"] = False
                state["bulletPositions"][bulletIndex] = int(state.get("playerPosition", 0) or 0)
                state["bulletDirections"][bulletIndex] = -1
                state["_lastBulletIndexLeft"] = bulletIndex
                break

    def _shoot_right(self, state: Dict[str, Any]) -> None:
        last = int(state.get("_lastBulletIndexRight", 0) or 0)
        bulletIndex = last
        for _ in range(MAX_BULLETS):
            bulletIndex = (bulletIndex + 1) % MAX_BULLETS
            if not bool(state["isBulletActive"][bulletIndex]):
                state["isBulletActive"][bulletIndex] = True
                state["isShootingLeft"] = False
                state["isShootingRight"] = True
                state["bulletPositions"][bulletIndex] = int(state.get("playerPosition", 0) or 0)
                state["bulletDirections"][bulletIndex] = 1
                state["_lastBulletIndexRight"] = bulletIndex
                break

    def _update_player_position(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        active = int(state.get("activeEnemyCount", 0) or 0)
        if active == 0:
            return

        waves = list(state.get("enemyWaves", []) or [])
        pp = int(state.get("playerPosition", n // 2) or n // 2)
        closest = int(state.get("closestEnemyPosition", -1) or -1)

        isTouched = False
        for i in range(active):
            if i >= len(waves):
                break
            w = waves[i]
            if bool(w.get("isAlive", False)) and abs(int(w.get("position", 0)) - pp) <= 1:
                isTouched = True
                break

        if isTouched:
            self._start_game_over_animation(state)
            return

        distToClosest = abs(pp - closest) if closest != -1 else 999999
        if distToClosest <= MAX_PLAYER_MOVE_DISTANCE:
            if closest < pp:
                if pp < (n - 1 - MAX_PLAYER_MOVE_DISTANCE):
                    pp += 1
            else:
                if pp > MAX_PLAYER_MOVE_DISTANCE:
                    pp -= 1
        else:
            start = int(state.get("playerStartPosition", n // 2) or n // 2)
            if pp < start:
                pp += 1
            elif pp > start:
                pp -= 1
        state["playerPosition"] = int(pp)

    # drawEnemies() contains logic: compute closest AND collision handling AND activeEnemyCount--
    def _draw_enemies_logic_only(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        waves = list(state.get("enemyWaves", []) or [])
        active = int(state.get("activeEnemyCount", 0) or 0)
        pp = int(state.get("playerPosition", n // 2) or n // 2)

        state["closestEnemyPosition"] = -1
        state["closestEnemyIndex"] = -1
        closestDist = n

        # NOTE: activeEnemyCount is decremented on kill, which affects the loop bound in Arduino.
        i = 0
        while i < active:
            if i >= len(waves):
                break
            w = waves[i]
            if bool(w.get("isAlive", False)):
                epos = int(w.get("position", 0) or 0)
                dist = abs(epos - pp)
                if dist < closestDist:
                    closestDist = dist
                    state["closestEnemyPosition"] = epos
                    state["closestEnemyIndex"] = i

                # bullet collision checks
                for bi in range(MAX_BULLETS):
                    if bool(state["isBulletActive"][bi]):
                        bpos = int(state["bulletPositions"][bi])
                        dist2 = abs(epos - bpos)
                        if dist2 <= 1:
                            state["isBulletActive"][bi] = False
                            w["isAlive"] = False
                            active -= 1  # critical quirk
                            state["bulletPositions"][bi] = pp
                            state["enemiesKilled"] = int(state.get("enemiesKilled", 0) or 0) + 1
                            break
            i += 1

        state["activeEnemyCount"] = max(0, int(active))
        state["enemyWaves"] = waves

    # ===== Rendering helpers mirroring drawPlayer/drawEnemies/bullets =====

    def _draw_player(self, px: List[RGB], state: Dict[str, Any]) -> None:
        n = len(px)
        pp = int(state.get("playerPosition", n // 2) or n // 2)
        # playerPosition-2,-1,+1,+2 blue, center red at half brightness
        blue = (0, 0, PLAYER_BRIGHTNESS_BLUE)
        red = (int((PLAYER_BRIGHTNESS_RED / 2)) & 255, 0, 0)
        for off in (-2, -1, 1, 2):
            idx = pp + off
            if 0 <= idx < n:
                px[idx] = blue
        if 0 <= pp < n:
            px[pp] = red

    def _draw_enemies(self, px: List[RGB], state: Dict[str, Any]) -> None:
        # purely visual draw, state was updated in _draw_enemies_logic_only
        n = len(px)
        waves = list(state.get("enemyWaves", []) or [])
        active = int(state.get("activeEnemyCount", 0) or 0)
        for i in range(min(active, len(waves))):
            w = waves[i]
            if not bool(w.get("isAlive", False)):
                continue
            epos = int(w.get("position", 0) or 0)
            if 0 <= epos < n:
                rgb = _u32_to_rgb(int(w.get("color", 0xFFFFFF)))
                px[epos] = _scale_rgb(rgb, int(w.get("brightness", ENEMY_BRIGHTNESS)))

    def _draw_bullets(self, px: List[RGB], state: Dict[str, Any]) -> None:
        n = len(px)
        for bi in range(MAX_BULLETS):
            if bool(state["isBulletActive"][bi]):
                bpos = int(state["bulletPositions"][bi])
                if 0 <= bpos < n:
                    px[bpos] = _scale_rgb(BULLET_COLOR, BULLET_BRIGHTNESS)

    # ===== Game over animation (non-blocking) =====

    def _start_game_over_animation(self, state: Dict[str, Any]) -> None:
        # Begin non-blocking emulation of gameOverAnimation() + restartGame()
        state["_gameover_active"] = True
        state["_gameover_start_ms"] = int(state.get("_millis", 0) or 0)
        state["_knight_pos"] = 0
        state["_knight_dir"] = 1

        # restartGame happens AFTER animation in Arduino; we will do it when animation ends
        # but we must snapshot enemiesKilled/highScore logic now.
        killed = int(state.get("enemiesKilled", 0) or 0)
        hs = int(state.get("highestScore", 0) or 0)
        if killed > hs:
            state["highestScore"] = killed

    def _restart_game(self, state: Dict[str, Any]) -> None:
        n = int(state.get("_n", 1) or 1)
        # Reset waves and bullets like Arduino restartGame()
        waves = list(state.get("enemyWaves", []) or [])
        for w in waves:
            w["isAlive"] = False
        state["enemyWaves"] = waves
        state["activeEnemyCount"] = 0
        state["playerPosition"] = int(state.get("playerStartPosition", n // 2) or n // 2)
        for i in range(MAX_BULLETS):
            state["bulletPositions"][i] = int(state["playerPosition"])
            state["isBulletActive"][i] = False
        state["enemiesKilled"] = 0
        state["waveNumber"] = 1
        state["waveEndTime_ms"] = int(state.get("_millis", 0) or 0) + WAVE_END_TIMEOUT_MS

        # Create initial wave? Arduino relies on wave timer; leave for loop to startNewWave when due.
        state["closestEnemyPosition"] = -1
        state["closestEnemyIndex"] = -1

    def _anim_step(self, state: Dict[str, Any]) -> None:
        now_ms = int(state.get("_millis", 0) or 0)
        if bool(state.get("_gameover_active", False)):
            start = int(state.get("_gameover_start_ms", now_ms) or now_ms)
            # Update sweeping black pixel ("knight")
            n = int(state.get("_n", 1) or 1)
            kp = int(state.get("_knight_pos", 0) or 0)
            kd = int(state.get("_knight_dir", 1) or 1)
            kp += kd
            if kp <= 0 or kp >= n - 1:
                kd *= -1
            state["_knight_pos"] = kp
            state["_knight_dir"] = kd

            if now_ms - start >= GAME_OVER_ANIMATION_DURATION_MS:
                state["_gameover_active"] = False
                # restart game then show highscore for 2s
                self._restart_game(state)
                state["_show_highscore"] = True
                state["_show_highscore_start_ms"] = now_ms
        elif bool(state.get("_show_highscore", False)):
            start = int(state.get("_show_highscore_start_ms", now_ms) or now_ms)
            if now_ms - start >= 2000:
                state["_show_highscore"] = False

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Shooter (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter.")


def register_shooter_game_ino():
    effect = ShooterGameINO()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=288, mw=0, mh=0, fixed_dt=1/60))
    defn = BehaviorDef(
        "shooter_game_ino",
        title="Shooter (INO Port)",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
