from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import math
import random

@dataclass
class Entity:
    kind: str
    x: float
    y: float
    vx: float
    vy: float
    r: float
    alive: bool = True
    ttl: float = 999.0

def step_entities(ents: List[Entity], dt: float, bounds: Tuple[float,float]=(1.0,1.0), wrap: bool=True) -> None:
    w,h = float(bounds[0]), float(bounds[1])
    for e in ents:
        if not e.alive:
            continue
        e.x += e.vx * dt
        e.y += e.vy * dt
        e.ttl -= dt
        if e.ttl <= 0.0:
            e.alive = False
            continue
        if wrap:
            if e.x < 0: e.x += w
            if e.x >= w: e.x -= w
            if e.y < 0: e.y += h
            if e.y >= h: e.y -= h
        else:
            if e.x < 0 or e.x > w or e.y < 0 or e.y > h:
                e.alive = False

def collide(a: Entity, b: Entity, bounds: Tuple[float,float]=(1.0,1.0), wrap: bool=True) -> bool:
    if not (a.alive and b.alive):
        return False
    dx = a.x - b.x
    dy = a.y - b.y
    if wrap:
        w,h = float(bounds[0]), float(bounds[1])
        if dx >  w/2: dx -= w
        if dx < -w/2: dx += w
        if dy >  h/2: dy -= h
        if dy < -h/2: dy += h
    rr = a.r + b.r
    return (dx*dx + dy*dy) <= rr*rr

def prune(ents: List[Entity]) -> List[Entity]:
    return [e for e in ents if e.alive]

def spawn_asteroid(bounds=(1.0,1.0), speed=0.15, r=0.04) -> Entity:
    w,h = float(bounds[0]), float(bounds[1])
    side = random.randint(0,3)
    if side==0: x,y = 0.0, random.random()*h
    elif side==1: x,y = w, random.random()*h
    elif side==2: x,y = random.random()*w, 0.0
    else: x,y = random.random()*w, h
    ang = random.random()*math.tau
    vx,vy = math.cos(ang)*speed, math.sin(ang)*speed
    return Entity("asteroid", x,y, vx,vy, r, True, 999.0)

def spawn_shot(x: float, y: float, ang: float, speed=0.5, ttl=1.0, r=0.01) -> Entity:
    vx,vy = math.cos(ang)*speed, math.sin(ang)*speed
    return Entity("shot", x,y, vx,vy, r, True, ttl)
