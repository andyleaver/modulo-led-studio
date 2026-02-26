from __future__ import annotations
from typing import Dict, Any, List, Tuple
from behaviors.registry import register_effect
from behaviors.stateful import EffectContext, schema_defaults
from behaviors.state_runtime import clamp

RGB = Tuple[int,int,int]

@register_effect
class AsteroidsLite:
    key = "asteroids_lite"
    title = "Asteroids (Demo)"
    # use existing knobs:
    # color = bullets, color2 = asteroids, bg = ship, speed = speed, density = asteroid count (1..3), softness = asteroid hp (1..5)
    uses = ["color", "color2", "bg", "speed", "density", "softness", "purpose_f0","purpose_f1","purpose_i0","purpose_i1"]
    stateful = True

    def state_schema(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "fields": {
                "ship": {"type":"float","default": 0.0},
                "cool": {"type":"float","default": 0.0},
                "bullets": {"type":"list","default": []},   # list[float] positions
                "asteroids": {"type":"list","default": []}, # list[dict]{pos,hp,vel}
                "score": {"type":"int","default": 0},
                "ammo": {"type":"int","default": 30},
            }
        }

    def _count_from_density(self, dn: float) -> int:
        try: dn=float(dn)
        except Exception: dn=0.0
        if dn < 0: dn=0.0
        if dn > 1: dn=1.0
        return int(round(1 + dn*2))  # 1..3

    def _hp_from_softness(self, so: float) -> int:
        try: so=float(so)
        except Exception: so=0.0
        if so < 0: so=0.0
        if so > 1: so=1.0
        return int(round(1 + so*4))  # 1..5

    def reset(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext) -> None:
        state.clear()
        state.update(schema_defaults(self.state_schema()))
        n = int(ctx.layout.get("num_leds", 60) or 60)
        dn = float(params.get("density", 0.0) or 0.0)
        so = float(params.get("softness", 0.0) or 0.0)
        k = self._count_from_density(dn)
        hp = self._hp_from_softness(so)
        state["ship"] = float(n-3)
        state["cool"] = 0.0
        state["bullets"] = []
        # asteroids start near left
        ast = []
        for i in range(k):
            ast.append({"pos": float(2+i*3), "vel": float(2+i), "hp": hp})
        state["asteroids"] = ast
        state["score"] = 0
        state["ammo"] = int(params.get('purpose_i0', 30) or 30)

    def tick(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext) -> None:
        n = int(ctx.layout.get("num_leds", 60) or 60)
        spd = float(params.get("speed", 1.0) or 1.0)
        dn = float(params.get("density", 0.0) or 0.0)
        so = float(params.get("softness", 0.0) or 0.0)
        k = self._count_from_density(dn)
        hp0 = self._hp_from_softness(so)

        # ensure asteroid list size
        ast = state.get("asteroids")
        if not isinstance(ast, list):
            ast = []
        if len(ast) != k:
            ast = ast[:k]
            while len(ast) < k:
                ast.append({"pos": float(2+len(ast)*3), "vel": float(2+len(ast)), "hp": hp0})
            state["asteroids"] = ast

        # cooldown & auto-fire bullets (purpose_f1 controls fire rate)
        try:
            fire_ctl = float(params.get('purpose_f1', 0.0) or 0.0)
        except Exception:
            fire_ctl = 0.0
        fire_rate = 0.35 - max(0.0, min(1.0, fire_ctl)) * 0.25  # 0.35..0.10
        cool = float(state.get("cool", 0.0))
        cool -= ctx.dt
        if cool <= 0.0:
            # fire from ship
            ship = float(state.get("ship", n-3))
            bullets = state.get("bullets")
            if not isinstance(bullets, list): bullets=[]
            ammo = int(state.get('ammo', 30))
            if ammo > 0 and len(bullets) < 3:
                bullets.append(ship-1.0)
                state['ammo'] = ammo - 1
                state['bullets'] = bullets
            cool = fire_rate
        state["cool"] = cool

        # move bullets left
        bullets = state.get("bullets")
        if not isinstance(bullets, list): bullets=[]
        nb=[]
        for b in bullets:
            b = float(b) - spd*ctx.dt*25.0
            if b >= 0.0:
                nb.append(b)
        bullets = nb

        # move asteroids right slowly, wrap
        for a in ast:
            a["pos"] = float(a.get("pos",0.0)) + float(a.get("vel",2.0))*spd*ctx.dt*3.0
            if a["pos"] > (n-1):
                a["pos"] = 0.0
            if int(a.get("hp",0)) <= 0:
                a["hp"] = hp0
                a["pos"] = 0.0

        # collisions bullet-asteroid
        score = int(state.get("score", 0))
        for bi in range(len(bullets)):
            b = bullets[bi]
            hit = False
            for a in ast:
                if abs(float(a.get("pos",0.0)) - b) <= 0.6 and int(a.get("hp",0)) > 0:
                    a["hp"] = int(a.get("hp",0)) - 1
                    score += 1
                    hit = True
                    break
            if hit:
                bullets[bi] = -9999.0
        bullets = [b for b in bullets if b >= 0.0]
        state["bullets"] = bullets
        state["score"] = score

                # ship control (purpose_f0): 0..1 maps to strip position
        try:
            ship_ctl = float(params.get('purpose_f0', 0.0) or 0.0)
        except Exception:
            ship_ctl = 0.0
        ship_ctl = 0.0 if ship_ctl < 0.0 else (1.0 if ship_ctl > 1.0 else ship_ctl)
        state['ship'] = float(ship_ctl * float(n-1))


    def render(self, state: Dict[str, Any], params: Dict[str, Any], ctx: EffectContext, out: List[RGB]) -> None:
        n = len(out)
        ship_col = params.get("bg", (0,255,0))
        bullet_col = params.get("color", (255,255,255))
        ast_col = params.get("color2", (0,0,255))

        ship = int(round(float(state.get("ship", n-3))))
        if 0 <= ship < n:
            out[ship] = (int(ship_col[0])&255, int(ship_col[1])&255, int(ship_col[2])&255)

        bullets = state.get("bullets")
        if isinstance(bullets, list):
            for b in bullets:
                i = int(round(float(b)))
                if 0 <= i < n:
                    out[i] = (int(bullet_col[0])&255, int(bullet_col[1])&255, int(bullet_col[2])&255)

        ast = state.get("asteroids")
        if isinstance(ast, list):
            for a in ast:
                if int(a.get("hp",0)) <= 0:
                    continue
                i = int(round(float(a.get("pos",0.0))))
                if 0 <= i < n:
                    out[i] = (int(ast_col[0])&255, int(ast_col[1])&255, int(ast_col[2])&255)

    def arduino_emit_stateful(self, *, layer_id: int, params: dict, layout: dict) -> str:
        return ""
