from __future__ import annotations

"""
shader_math_v1 (shared math helpers)

Goal: remove duplicated tiny math utilities scattered across effects
(particles/fields/boids), without changing behavior semantics.

This is NOT an "effect". It's a shared primitive utility module.
"""

from typing import Tuple
import math

RGB = Tuple[int, int, int]

def clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def hash_u32(x: int) -> int:
    x = (x ^ 0x9E3779B9) & 0xFFFFFFFF
    x = (x * 0x85EBCA6B) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) & 0xFFFFFFFF
    x = (x * 0xC2B2AE35) & 0xFFFFFFFF
    x = (x ^ (x >> 16)) & 0xFFFFFFFF
    return x & 0xFFFFFFFF

def u01(h: int) -> float:
    return float(h & 0xFFFFFF) / float(0x1000000)

def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    # Matches existing effect-local implementations.
    h = (h % 1.0) * 6.0
    i = int(h) % 6
    f = h - float(i)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    if i == 0: r,g,b = v,t,p
    elif i == 1: r,g,b = q,v,p
    elif i == 2: r,g,b = p,v,t
    elif i == 3: r,g,b = p,q,v
    elif i == 4: r,g,b = t,p,v
    else: r,g,b = v,p,q
    return (int(r*255) & 255, int(g*255) & 255, int(b*255) & 255)

def add_rgb(a: RGB, b: RGB) -> RGB:
    return (min(255, a[0] + b[0]), min(255, a[1] + b[1]), min(255, a[2] + b[2]))

def gauss(d: float, sigma: float) -> float:
    # exp(-(d^2)/(2*sigma^2))
    if sigma <= 1e-9:
        return 0.0
    return math.exp(-(d*d) / (2.0 * sigma * sigma))
