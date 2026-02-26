"""CA Module Runner (preview + export)

This behavior runs a registered CA module from runtime/ca_modules_v1.

Params:
  module_name: str  (e.g. 'life_B3S23' or 'elem_rule30')
  speed: float      update rate control
  density: float    init density (0..1)
  rule: int         for elem1d modules
  Bmask/Smask: int  for life2d modules (bitmask of neighbor counts)

Export:
  Implemented via Arduino exporter codegen: module dispatch + module step bodies.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]

from runtime.ca_modules_v1 import get_ca_module
from runtime.shader_math_v1 import clamp01
from behaviors.registry import BehaviorDef, register


def _preview_emit(
    *,
    num_leds: int,
    params: Dict,
    t: float,
    state=None,
    layout=None,
    dt: float = 0.0,
    **_kwargs,
) -> List[RGB]:
    module_name = str(params.get("module_name", "life_B3S23"))
    mod = get_ca_module(module_name)
    if mod is None:
        # Visible failure mode: magenta
        return [(255, 0, 255)] * num_leds

    # init / buffers
    if state is None:
        state = {}
    src = state.get("ca_src")
    dst = state.get("ca_dst")
    if src is None or dst is None or len(src) != num_leds or len(dst) != num_leds:
        src = [0] * num_leds
        dst = [0] * num_leds
        state["ca_src"] = src
        state["ca_dst"] = dst
        state["ca_accum"] = 0.0
        # initialize
        dens = clamp01(float(params.get("density", 0.25)))
        # simple deterministic init based on index
        for i in range(num_leds):
            src[i] = 1 if (((i * 1103515245 + 12345) >> 16) & 0xFFFF) < int(dens * 65535) else 0

    # determine grid
    if layout is not None and getattr(layout, "shape", None) == "cells":
        w = int(getattr(layout, "width", 0) or getattr(layout, "mw", 0) or 0)
        h = int(getattr(layout, "height", 0) or getattr(layout, "mh", 0) or 0)
        if w <= 0 or h <= 0:
            # fallback to square-ish
            w = int(num_leds**0.5)
            h = max(1, num_leds // max(1, w))
    else:
        w, h = num_leds, 1

    # stepping
    speed = max(0.0, float(params.get("speed", 1.0)))
    step_hz = 1.0 + 30.0 * speed
    accum = float(state.get("ca_accum", 0.0)) + float(dt)
    did_step = False
    while accum >= (1.0 / step_hz):
        accum -= (1.0 / step_hz)
        did_step = True
        if mod.kind == "life2d":
            Bmask = int(params.get("Bmask", (1 << 3)))
            Smask = int(params.get("Smask", (1 << 2) | (1 << 3)))
            mod.py_step(src, dst, w, h, {"B": _bits_to_list(Bmask), "S": _bits_to_list(Smask)})
        else:
            rule = int(params.get("rule", 30)) & 0xFF
            mod.py_step(src, dst, w, h, {"rule": rule})
        src, dst = dst, src
        state["ca_src"], state["ca_dst"] = src, dst
    state["ca_accum"] = accum

    # render
    # alive -> white, dead -> black, optionally color via params
    br = clamp01(float(params.get("brightness", 1.0)))
    on = int(255 * br)
    if did_step:
        # slight sparkle to show animation (preview only)
        pass
    return [(on, on, on) if src[i] else (0, 0, 0) for i in range(num_leds)]


def _bits_to_list(mask: int) -> List[int]:
    out: List[int] = []
    for i in range(9):
        if mask & (1 << i):
            out.append(i)
    return out


def _arduino_emit(*args, **kwargs):
    # Arduino export is handled by the exporter (behavior mapping + codegen).
    return None


def register_ca_module():
    return register(
        BehaviorDef(
            "ca_module",
            title="CA Module",
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            uses=["state"],
        )
    )
