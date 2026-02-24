from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import math
import random

RGB = Tuple[int,int,int]

class DeterministicRNG:
    """Deterministic RNG for stateful sims (preview)."""
    def __init__(self, seed: int = 0):
        self._rng = random.Random(int(seed) & 0xFFFFFFFF)

    def rand(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, seq):
        return self._rng.choice(seq)

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo: return lo
    if x > hi: return hi
    return x

def wrap(x: float, lo: float, hi: float) -> float:
    span = hi - lo
    if span <= 0:
        return lo
    while x < lo:
        x += span
    while x >= hi:
        x -= span
    return x

@dataclass
class Entity:
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    r: float = 0.5  # radius for collisions
    alive: bool = True
    tag: str = ""

def entities_from_state(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    lst = state.get("entities")
    if not isinstance(lst, list):
        lst = []
        state["entities"] = lst
    return lst

def spawn_entity(state: Dict[str, Any], *, x: float, y: float, vx: float=0.0, vy: float=0.0, r: float=0.5, tag: str="") -> int:
    lst = entities_from_state(state)
    nid = int(state.get("_next_eid", 1))
    state["_next_eid"] = nid + 1
    ent = {"id": nid, "x": float(x), "y": float(y), "vx": float(vx), "vy": float(vy), "r": float(r), "alive": True, "tag": str(tag)}
    lst.append(ent)
    return nid

def kill_entity(state: Dict[str, Any], eid: int) -> None:
    lst = entities_from_state(state)
    for e in lst:
        if int(e.get("id", -1)) == int(eid):
            e["alive"] = False
            return

def purge_dead(state: Dict[str, Any]) -> None:
    lst = entities_from_state(state)
    state["entities"] = [e for e in lst if bool(e.get("alive", True))]

def step_entities(state: Dict[str, Any], dt: float, *, bounds: Optional[Tuple[float,float,float,float]]=None, bounce: bool=False, wrap_xy: bool=False) -> None:
    """Advance all entities by dt.
    bounds: (xmin,xmax,ymin,ymax) in same units as positions.
    bounce: reflect velocity at bounds.
    wrap_xy: wrap around bounds.
    """
    lst = entities_from_state(state)
    for e in lst:
        if not bool(e.get("alive", True)):
            continue
        e["x"] = float(e.get("x",0.0)) + float(e.get("vx",0.0))*dt
        e["y"] = float(e.get("y",0.0)) + float(e.get("vy",0.0))*dt
        if bounds:
            xmin,xmax,ymin,ymax = bounds
            if wrap_xy:
                e["x"] = wrap(e["x"], xmin, xmax)
                e["y"] = wrap(e["y"], ymin, ymax)
            elif bounce:
                # x
                if e["x"] < xmin:
                    e["x"] = xmin
                    e["vx"] = abs(float(e.get("vx",0.0)))
                if e["x"] > xmax:
                    e["x"] = xmax
                    e["vx"] = -abs(float(e.get("vx",0.0)))
                # y
                if e["y"] < ymin:
                    e["y"] = ymin
                    e["vy"] = abs(float(e.get("vy",0.0)))
                if e["y"] > ymax:
                    e["y"] = ymax
                    e["vy"] = -abs(float(e.get("vy",0.0)))

def circle_collide(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ax, ay = float(a.get("x",0.0)), float(a.get("y",0.0))
    bx, by = float(b.get("x",0.0)), float(b.get("y",0.0))
    ar, br = float(a.get("r",0.5)), float(b.get("r",0.5))
    dx = ax - bx; dy = ay - by
    return (dx*dx + dy*dy) <= (ar+br)*(ar+br)

def find_collisions(state: Dict[str, Any], *, tag_a: str="", tag_b: str="") -> List[Tuple[int,int]]:
    lst = [e for e in entities_from_state(state) if bool(e.get("alive",True))]
    hits=[]
    for i in range(len(lst)):
        for j in range(i+1, len(lst)):
            ea, eb = lst[i], lst[j]
            if tag_a and str(ea.get("tag","")) != tag_a and str(eb.get("tag","")) != tag_a:
                continue
            if tag_b:
                ta, tb = str(ea.get("tag","")), str(eb.get("tag",""))
                if not ((ta==tag_a and tb==tag_b) or (ta==tag_b and tb==tag_a)):
                    continue
            if circle_collide(ea, eb):
                hits.append((int(ea.get("id",0)), int(eb.get("id",0))))
    return hits

def grid_xy_from_strip(i: int, w: int, h: int) -> Tuple[int,int]:
    """Map strip index to x,y in row-major w*h (for simple sims on strip)."""
    i = int(i)
    x = i % int(w)
    y = i // int(w)
    return x, y

def strip_index_from_xy(x: int, y: int, w: int, h: int) -> int:
    x=int(x); y=int(y)
    if x<0 or y<0 or x>=w or y>=h:
        return -1
    return y*w + x

def spawn_bullet(state: Dict[str, Any], *, x: float, y: float=0.0, vx: float=-10.0, vy: float=0.0, r: float=0.25, tag: str="bullet") -> int:
    return spawn_entity(state, x=x, y=y, vx=vx, vy=vy, r=r, tag=tag)

def apply_projectile_hits(state: Dict[str, Any], *, bullet_tag: str="bullet", target_tag: str="target",
                          damage: int=1) -> int:
    """Detect bullet-target collisions. Kills bullet, decrements target hp (stored in entity 'hp').
    Returns number of hits applied.
    """
    lst = entities_from_state(state)
    # build lists
    bullets = [e for e in lst if bool(e.get("alive",True)) and str(e.get("tag","")) == bullet_tag]
    targets = [e for e in lst if bool(e.get("alive",True)) and str(e.get("tag","")) == target_tag]
    hits = 0
    for b in bullets:
        for t in targets:
            if not bool(b.get("alive",True)) or not bool(t.get("alive",True)):
                continue
            if circle_collide(b, t):
                b["alive"] = False
                hp = int(t.get("hp", 1))
                hp -= int(damage)
                t["hp"] = hp
                hits += 1
                if hp <= 0:
                    t["alive"] = False
                break
    if hits:
        purge_dead(state)
    return hits
