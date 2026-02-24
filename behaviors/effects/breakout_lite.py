from __future__ import annotations
from typing import Dict, Any, List, Tuple
from behaviors.registry import register_effect
from behaviors.stateful import EffectContext, schema_defaults
from behaviors.state_runtime import clamp

RGB = Tuple[int,int,int]

def _blocks_from_density(dn: float) -> int:
    # 3..8 blocks (fits Arduino ST_I slots)
    try:
        dn=float(dn)
    except Exception:
        dn=0.0
    dn = 0.0 if dn < 0.0 else (1.0 if dn > 1.0 else dn)
    return int(round(3 + dn * 5))

def _health_from_softness(so: float) -> int:
    # 1..5 hp
    try:
        so=float(so)
    except Exception:
        so=0.0
    so = 0.0 if so < 0.0 else (1.0 if so > 1.0 else so)
    return int(round(1 + so * 4))

@register_effect
class BreakoutLite:
    key = "breakout_lite"
    title = "Breakout (Demo)"
    # Reuse existing knobs (no new params needed):
    # color = ball, color2 = blocks, bg = paddle, width = paddle width, speed = sim speed,
    # density = blocks count, softness = block health
    uses = ["color", "color2", "bg", "width", "speed", "density", "softness"]
    stateful = True

    def state_schema(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "fields": {
                "ball_pos": {"type": "float", "default": 0.0},
                "ball_vel": {"type": "float", "default": -1.0},
                "paddle":   {"type": "float", "default": 0.0},
                "score":    {"type": "int",   "default": 0},
                "blocks":   {"type": "list",  "default": []},  # list[int] hp
            }
        }

    def reset(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext) -> None:
        state.clear()
        state.update(schema_defaults(self.state_schema()))
        n = int(ctx.layout.get("num_leds", 60) or 60)
        dn = float(params.get("density", 0.0) or 0.0)
        so = float(params.get("softness", 0.0) or 0.0)
        blocks = _blocks_from_density(dn)
        hp = _health_from_softness(so)
        state["blocks"] = [hp for _ in range(blocks)]
        state["ball_pos"] = float(n-5)
        state["ball_vel"] = -1.0
        state["paddle"] = float(n-3)
        state["score"] = 0

    def tick(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext) -> None:
        n = int(ctx.layout.get("num_leds", 60) or 60)
        spd = float(params.get("speed", 1.0) or 1.0)
        width = int(params.get("width", 6) or 6)
        if width < 2: width = 2
        if width > max(2, n//2): width = max(2, n//2)

        dn = float(params.get("density", 0.0) or 0.0)
        so = float(params.get("softness", 0.0) or 0.0)
        blocks = _blocks_from_density(dn)
        hp = _health_from_softness(so)
        # ensure blocks list correct size
        bl = state.get("blocks")
        if not isinstance(bl, list) or len(bl) != blocks:
            state["blocks"] = [hp for _ in range(blocks)]
            bl = state["blocks"]

        # basic 1D breakout: blocks occupy first third of strip, paddle last 20%
        block_region = max(6, n//3)
        block_w = max(1, block_region // blocks)

        # paddle auto-follow ball for demo (AI)
        paddle = float(state.get("paddle", n-3))
        ball_pos = float(state.get("ball_pos", n-5))
        # move paddle toward ball with limited speed
        paddle += clamp(ball_pos - paddle, -1.0, 1.0) * spd * ctx.dt * 25.0
        paddle = clamp(paddle, block_region + width/2, n-1-width/2)
        state["paddle"] = paddle

        # advance ball
        vel = float(state.get("ball_vel", -1.0))
        # keep vel non-zero
        if vel == 0.0: vel = -1.0
        ball_pos += vel * spd * ctx.dt * 30.0

        # wall bounce
        if ball_pos < 0.0:
            ball_pos = 0.0
            vel = abs(vel)
        if ball_pos > (n-1):
            ball_pos = float(n-1)
            vel = -abs(vel)

        # block collision (if ball in region)
        bi = int(ball_pos // block_w) if block_w > 0 else 0
        if ball_pos < block_region and 0 <= bi < blocks and bl[bi] > 0:
            bl[bi] = int(bl[bi]) - 1
            state["score"] = int(state.get("score", 0)) + 1
            vel = abs(vel)  # bounce right

        # paddle collision (simple): if ball hits paddle zone moving right, bounce left
        if vel > 0.0:
            pad_left = paddle - width/2
            pad_right = paddle + width/2
            if ball_pos >= pad_left and ball_pos <= pad_right:
                vel = -abs(vel)
                ball_pos = pad_left - 0.1

        # win condition -> reset blocks when all cleared
        if all(int(x) <= 0 for x in bl):
            # refill blocks but keep score increasing
            state["blocks"] = [hp for _ in range(blocks)]
            vel = -abs(vel)
            ball_pos = float(n-5)

        state["ball_pos"] = ball_pos
        state["ball_vel"] = vel

    def render(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext, out: List[RGB]) -> None:
        n = len(out)
        dn = float(params.get("density", 0.0) or 0.0)
        blocks = _blocks_from_density(dn)
        bl = state.get("blocks")
        if not isinstance(bl, list) or len(bl) != blocks:
            bl = [1 for _ in range(blocks)]

        # colors
        ball = params.get("color", (255,255,255))
        blocks_col = params.get("color2", (0,0,255))
        paddle_col = params.get("bg", (255,255,0))

        # draw blocks in first third
        block_region = max(6, n//3)
        block_w = max(1, block_region // blocks)
        for b in range(blocks):
            if int(bl[b]) <= 0: 
                continue
            start = b*block_w
            end = min(block_region, start+block_w)
            for i in range(start, end):
                out[i] = (int(blocks_col[0])&255, int(blocks_col[1])&255, int(blocks_col[2])&255)

        # draw paddle in last part
        width = int(params.get("width", 6) or 6)
        if width < 2: width = 2
        paddle = float(state.get("paddle", n-3))
        pl = int(round(paddle - width/2))
        pr = int(round(paddle + width/2))
        for i in range(max(0,pl), min(n, pr+1)):
            out[i] = (int(paddle_col[0])&255, int(paddle_col[1])&255, int(paddle_col[2])&255)

        # draw ball
        bp = int(round(float(state.get("ball_pos", n-5))))
        if 0 <= bp < n:
            out[bp] = (int(ball[0])&255, int(ball[1])&255, int(ball[2])&255)

    def arduino_emit_stateful(self, *, layer_id: int, params: dict, layout: dict) -> str:
        # Not used: Arduino implementation is embedded in exporter template via beh id 9.
        return ""
