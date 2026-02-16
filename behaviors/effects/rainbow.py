from __future__ import annotations
SHIPPED = True

from typing import List, Tuple
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int,int,int]

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    # h 0..1
    h = h % 1.0
    s = _clamp01(s)
    v = _clamp01(v)
    i = int(h*6.0)
    f = (h*6.0) - i
    p = v*(1.0-s)
    q = v*(1.0-f*s)
    t = v*(1.0-(1.0-f)*s)
    i = i % 6
    if i==0: r,g,b=v,t,p
    elif i==1: r,g,b=q,v,p
    elif i==2: r,g,b=p,v,t
    elif i==3: r,g,b=p,q,v
    elif i==4: r,g,b=t,p,v
    else: r,g,b=v,p,q
    return (int(r*255)&255, int(g*255)&255, int(b*255)&255)

def _apply_brightness(rgb, br: float):
    br = _clamp01(float(br))
    r,g,b = rgb
    return (int(r*br)&255, int(g*br)&255, int(b*br)&255)

def _preview_emit(*, num_leds: int, params: dict, t: float) -> List[RGB]:
    n = max(1, int(num_leds))
    br = float(params.get("brightness", 1.0))
    sp = max(0.0, float(params.get("speed", 1.0)))
    off = int(params.get("hue_offset", 0)) & 255
    span = float(params.get("hue_span", 1.0))  # cycles across strip
    out=[]
    base = (off/255.0) + (t*sp*0.15)
    for i in range(n):
        h = base + (i/max(1,n-1))*span
        rgb = _hsv_to_rgb(h, 1.0, 1.0)
        out.append(_apply_brightness(rgb, br))
    return out

def _arduino_emit(*, layout: dict, params: dict) -> str:
    return ""

def register_rainbow():
    return register(BehaviorDef(
        "rainbow",
        title="Rainbow",
        uses=["brightness","speed","hue_offset","hue_span"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
