from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple, Optional

from behaviors.registry import BehaviorDef, register
from behaviors.state import rng_load, rng_save
from behaviors.stateful_adapter import StatefulEffect, AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]
USES = ["preview", "arduino"]

def _map_int(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    if in_max == in_min:
        return out_min
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

class BlocksBallGameINO(StatefulEffect):
    """Faithful port of the 'Ball variables / Blocks' sketch section in 'game visuals.ino'."""

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 288) or 288)
        seed = int(params.get("seed", 1)) & 0xFFFFFFFF
        state.clear()
        state["_n"] = n
        state["seed"] = seed

        rng = rng_load(state, seed=seed)

        state["ballPosition"] = int(rng.randrange(n))
        state["ballDirection"] = -1 if int(rng.randrange(2)) == 0 else 1
        state["ballSize"] = 1
        state["ballSpeed"] = 1

        state["numBlocks"] = 20
        state["maxBlockHealth"] = 5
        # blockHealthByColor: {0,2,4,5} but random(1,4) -> picks 1..3 => 2,4,5
        state["blockHealthByColor"] = [0, 2, 4, 5]
        blockPositions: List[int] = []
        blockHealth: List[int] = []
        blockColors: List[int] = []

        for _ in range(state["numBlocks"]):
            blockPositions.append(int(rng.randrange(n)))
            h = int(state["blockHealthByColor"][int(rng.randrange(1, 4))])
            blockHealth.append(h)
            blockColors.append(h)  # matches ino
        state["blockPositions"] = blockPositions
        state["blockHealth"] = blockHealth
        state["blockColors"] = blockColors
        state["allBlocksDestroyed"] = False

        rng_save(state, rng)

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        n = int(params.get("_num_leds", state.get("_n", 1)) or state.get("_n", 1))
        ballPosition = int(state.get("ballPosition", 0) or 0)
        ballDirection = int(state.get("ballDirection", 1) or 1)
        ballSize = int(state.get("ballSize", 1) or 1)
        ballSpeed = int(state.get("ballSpeed", 1) or 1)

        numBlocks = int(state.get("numBlocks", 20) or 20)
        blockPositions = list(state.get("blockPositions", []) or [])
        blockHealth = list(state.get("blockHealth", []) or [])
        # Move ball with speed (exactly as ino; one 'loop' per tick)
        for _step in range(ballSpeed):
            nextBallPosition = ballPosition + ballDirection
            if nextBallPosition <= 0 or nextBallPosition >= n - ballSize:
                ballDirection *= -1
                break

            ballCollidedWithBlock = False
            for i in range(min(numBlocks, len(blockPositions), len(blockHealth))):
                if blockHealth[i] > 0 and nextBallPosition >= blockPositions[i] and nextBallPosition < blockPositions[i] + ballSize:
                    blockHealth[i] -= 1
                    if blockHealth[i] == 0:
                        # continue; (ino continues but still reverses direction only if not zero)
                        pass
                    ballDirection *= -1
                    ballCollidedWithBlock = True
                    break
            if not ballCollidedWithBlock:
                ballPosition = nextBallPosition

        # all blocks destroyed?
        allDestroyed = True
        for i in range(min(numBlocks, len(blockHealth))):
            if blockHealth[i] > 0:
                allDestroyed = False
                break

        if allDestroyed:
            # In the Arduino sketch, the strip is painted solid blue for this
            # frame, THEN blocks are respawned. To match what you see on real
            # LEDs, we latch a one-frame flash.
            state["_blue_flash"] = 1

            # respawnBlocks()
            rng = rng_load(state, seed=int(state.get("seed", 1)))
            bhc = list(state.get("blockHealthByColor", [0, 2, 4, 5]))
            blockPositions = []
            blockHealth = []
            blockColors = []
            for _ in range(numBlocks):
                blockPositions.append(int(rng.randrange(n)))
                h = int(bhc[int(rng.randrange(1, 4))])
                blockHealth.append(h)
                blockColors.append(h)
            state["allBlocksDestroyed"] = False
            state["blockPositions"] = blockPositions
            state["blockHealth"] = blockHealth
            state["blockColors"] = blockColors
            rng_save(state, rng)
        else:
            state["allBlocksDestroyed"] = False
            state["blockHealth"] = blockHealth
            state["blockPositions"] = blockPositions

        state["ballPosition"] = int(ballPosition) % n
        state["ballDirection"] = int(ballDirection) if int(ballDirection) != 0 else 1
        state["_n"] = n

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        px: List[RGB] = [(0, 0, 0)] * n

        # One-frame "all blue" flash when all blocks are destroyed.
        if int(state.get("_blue_flash", 0) or 0) > 0:
            state["_blue_flash"] = max(0, int(state.get("_blue_flash", 0) or 0) - 1)
            return [(0, 0, 255)] * n

        numBlocks = int(state.get("numBlocks", 20) or 20)
        blockPositions = list(state.get("blockPositions", []) or [])
        blockHealth = list(state.get("blockHealth", []) or [])
        blockColors = list(state.get("blockColors", []) or [])
        maxBlockHealth = int(state.get("maxBlockHealth", 5) or 5)

        ballPosition = int(state.get("ballPosition", 0) or 0)
        ballSize = int(state.get("ballSize", 1) or 1)

        # Normal render path.

        for i in range(n):
            if i >= ballPosition and i < ballPosition + ballSize:
                px[i] = (255, 0, 0)  # red ball
            else:
                isBlock = False
                for j in range(min(numBlocks, len(blockPositions), len(blockHealth))):
                    if blockHealth[j] > 0 and i == int(blockPositions[j]) % n:
                        colorIntensity = _map_int(int(blockHealth[j]), 1, maxBlockHealth, 0, 255)
                        blockColor = int(blockColors[j]) if j < len(blockColors) else 0
                        r = 0
                        g = 0
                        b = 0
                        if blockColor == 1:
                            g = colorIntensity  # matches ino comment, though it's green channel
                        elif blockColor == 2:
                            b = colorIntensity
                        else:
                            g = colorIntensity
                        px[i] = (r & 255, g & 255, b & 255)
                        isBlock = True
                        break
                if not isBlock:
                    px[i] = (0, 0, 0)
        return px

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Blocks+Ball (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter.")

def register_blocks_ball_game_ino():
    effect = BlocksBallGameINO()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=288, mw=0, mh=0, fixed_dt=1/60))
    defn = BehaviorDef(
        "blocks_ball_game_ino",
        title="Blocks + Ball (INO Port)",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
