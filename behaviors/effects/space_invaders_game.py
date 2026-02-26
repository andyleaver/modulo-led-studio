from __future__ import annotations

SHIPPED = True

import random
from typing import Dict, Any, List

from behaviors.registry import BehaviorDef, register

USES = ["preview", "arduino"]


def _init(state: Dict[str, Any], mw: int, mh: int, seed: int, params: Dict[str, Any]):
    rng = random.Random(int(seed) & 0xFFFFFFFF)
    state.clear()
    state["seed"] = int(seed) & 0xFFFFFFFF
    state["mw"] = int(mw)
    state["mh"] = int(mh)

    cols = int(params.get("inv_cols", 8) or 8)
    rows = int(params.get("inv_rows", 3) or 3)
    cols = max(4, min(cols, max(4, mw - 2)))
    rows = max(2, min(rows, 6))

    start_x = max(1, (mw - cols) // 2)
    start_y = 1

    invaders = []
    for ry in range(rows):
        for cx in range(cols):
            invaders.append([start_x + cx, start_y + ry])
    state["invaders"] = invaders
    state["dir"] = 1
    state["step_acc"] = 0.0

    state["player_x"] = mw // 2
    state["player_y"] = mh - 2

    state["bullets"] = []
    state["shoot_acc"] = 0.0
    state["score"] = 0


def _update(*, state: Dict[str, Any], params: Dict[str, Any], dt: float, t: float, audio=None):
    mw = int(params.get("_mw", state.get("mw", 24) or 24))
    mh = int(params.get("_mh", state.get("mh", 24) or 24))
    seed = int(params.get("seed", 1) or 1)

    if int(state.get("mw", -1)) != mw or int(state.get("mh", -1)) != mh or int(state.get("seed", -1)) != (seed & 0xFFFFFFFF) or "invaders" not in state:
        _init(state, mw, mh, seed, params)

    inv = state.get("invaders", [])
    bullets = state.get("bullets", [])

    mps = float(params.get("inv_moves_per_second", 6.0) or 6.0)
    mps = max(0.5, min(mps, 30.0))
    step_dt = 1.0 / mps

    acc = float(state.get("step_acc", 0.0) or 0.0) + float(dt)
    while acc >= step_dt:
        acc -= step_dt
        xs = [p[0] for p in inv] if inv else []
        minx = min(xs) if xs else mw // 2
        maxx = max(xs) if xs else mw // 2
        dirv = int(state.get("dir", 1) or 1)
        if (dirv > 0 and maxx + 1 >= mw - 1) or (dirv < 0 and minx - 1 <= 0):
            dirv *= -1
            state["dir"] = dirv
            for p in inv:
                p[1] = min(mh - 3, p[1] + 1)
        else:
            for p in inv:
                p[0] += dirv
    state["step_acc"] = acc

    # Player AI: systematically visit invader columns so we eventually clear edge stragglers.
    inv_xs = sorted({int(p[0]) for p in inv}) if inv else []
    px = int(state.get("player_x", mw // 2) or mw // 2)

    if inv_xs:
        seq = state.get("target_seq")
        if not isinstance(seq, list) or sorted(set(seq)) != inv_xs:
            seq = inv_xs[:]  # left->right order
            state["target_seq"] = seq
            state["target_idx"] = 0

        idx = int(state.get("target_idx", 0) or 0) % max(1, len(seq))
        tx = int(seq[idx])

        # Move faster if far away (up to 2 cells per update)
        if tx > px:
            px = min(mw - 1, px + (2 if (tx - px) > 1 else 1))
        elif tx < px:
            px = max(0, px - (2 if (px - tx) > 1 else 1))
        state["player_x"] = px
    else:
        # POST-CLEAR SWEEP: when invaders are gone, sweep across full width so bullets can hit remaining bricks.
        dir2 = int(state.get('sweep_dir', 1) or 1)
        px2 = int(state.get('player_x', px) or px)
        px2 += dir2
        if px2 <= 0:
            px2 = 0
            dir2 = 1
        elif px2 >= mw - 1:
            px2 = mw - 1
            dir2 = -1
        state['sweep_dir'] = dir2
        state['player_x'] = px2

    # Shooting
    sps = float(params.get("shots_per_second", 2.0) or 2.0)
    sps = max(0.2, min(sps, 20.0))
    state["shoot_acc"] = float(state.get("shoot_acc", 0.0) or 0.0) + float(dt)
    if state["shoot_acc"] >= (1.0 / sps):
        state["shoot_acc"] = 0.0
        px = int(state.get("player_x", mw // 2) or mw // 2)
        bullets.append([px, int(state.get("player_y", mh - 2) or mh - 2) - 1])
        # After each shot, advance to the next invader column target
        try:
            seq = state.get('target_seq')
            if isinstance(seq, list) and len(seq) > 0:
                state['target_idx'] = (int(state.get('target_idx', 0) or 0) + 1) % len(seq)
        except Exception:
            pass

    # Bullet move + collide
    new_b = []
    inv_map = {(int(p[0]), int(p[1])): p for p in inv}
    for b in bullets:
        bx, by = int(b[0]), int(b[1])
        by -= 1
        if by <= 0:
            continue
        if (bx, by) in inv_map:
            try:
                inv.remove(inv_map[(bx, by)])
            except Exception:
                pass
            state["score"] = int(state.get("score", 0) or 0) + 1
            continue
        new_b.append([bx, by])
    state["bullets"] = new_b


def _preview_emit(*, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]):
    mw = int(params.get("_mw", 24) or 24)
    mh = int(params.get("_mh", 24) or 24)
    out = [(0, 0, 0)] * int(num_leds)

    def _i(x: int, y: int) -> int:
        return int(y) * mw + int(x)

    for p in (state.get("invaders") or []):
        x, y = int(p[0]), int(p[1])
        if 0 <= x < mw and 0 <= y < mh:
            out[_i(x, y)] = (180, 0, 255)

    px = int(state.get("player_x", mw // 2) or mw // 2)
    py = int(state.get("player_y", mh - 2) or mh - 2)
    out[_i(px, py)] = (0, 150, 255)

    for b in (state.get("bullets") or []):
        x, y = int(b[0]), int(b[1])
        if 0 <= x < mw and 0 <= y < mh:
            out[_i(x, y)] = (255, 255, 255)

    return out


def _get_hit_targets(*, state: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    for i, p in enumerate(state.get("invaders") or []):
        try:
            targets.append({"kind": "invader", "entity_id": str(i), "x": int(p[0]), "y": int(p[1])})
        except Exception:
            pass
    return targets


def _apply_hit(*, state: Dict[str, Any], params: Dict[str, Any], hit: Dict[str, Any], target: Dict[str, Any]) -> bool:
    if str(target.get("kind", "")) != "invader":
        return False
    tx, ty = int(target.get("x", -999)), int(target.get("y", -999))
    inv = state.get("invaders") or []
    removed = False
    new_inv = []
    for p in inv:
        if int(p[0]) == tx and int(p[1]) == ty and not removed:
            removed = True
            continue
        new_inv.append(p)
    if removed:
        state["invaders"] = new_inv
        state["score"] = int(state.get("score", 0) or 0) + 1
    return removed



def _get_hit_events(*, state: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit bullet hits for cross-layer interaction.

    Only after ALL invaders are destroyed, bullets can affect other layers (e.g., shoot remaining bricks).
    """
    try:
        inv = state.get("invaders") or []
        if len(inv) > 0:
            return []
        hits: List[Dict[str, Any]] = []
        for b in (state.get("bullets") or []):
            try:
                hits.append({
                    "kind": "bullet",
                    "x": int(b[0]),
                    "y": int(b[1]),
                    "damage": 1,
                    "invaders_cleared": True,
                })
            except Exception:
                pass
        return hits
    except Exception:
        return []


def _get_hit_events(*, state: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit bullet hits for cross-layer interaction.

    Only after ALL invaders are destroyed, bullets can affect other layers (e.g., shoot remaining bricks).
    Emit a short vertical sweep to avoid skipping targets due to tick ordering.
    """
    try:
        invs = state.get("invaders") or []
        if len(invs) > 0:
            return []
        hits: List[Dict[str, Any]] = []
        for b in (state.get("bullets") or []):
            bx = int(b[0]); by = int(b[1])
            for yy in (by, by - 1, by - 2):
                hits.append({
                    "kind": "bullet",
                    "x": bx,
                    "y": yy,
                    "damage": 1,
                    "invaders_cleared": True,
                })
        return hits
    except Exception:
        return []

def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    raise RuntimeError("Space Invaders (Game) is preview-ready but Arduino export is not wired yet.")


def register_space_invaders_game():
    defn = BehaviorDef(
        "space_invaders_game",
        title="Space Invaders (Game)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = _update
    defn.get_hit_targets = _get_hit_targets
    defn.apply_hit = _apply_hit
    defn.get_hit_events = _get_hit_events
    register(defn)
