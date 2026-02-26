from __future__ import annotations
SHIPPED = True

"""Kernel DSL (Phase 3.4)

Shader-like per-pixel behavior defined by a single expression.

Preview:
- Expression is evaluated in a restricted AST sandbox.
- Inputs: x,y,t,seed,pi.

Export:
- Expression is compiled to C++ at export time (see export/arduino_exporter.py).
- Behavior id: kernel_dsl.
"""

from typing import Any, Dict, List, Tuple, Optional

from behaviors.registry import BehaviorDef, register
from runtime.kernel_dsl_v1 import compile_kernel_expr, KernelCompileError

RGB = Tuple[int, int, int]
USES = ["kernel_expr", "seed"]


def _arduino_emit(*, layout: dict, params: dict, ctx: dict) -> str:
    # Export path is implemented in the multi-layer exporter (behavior id mapping).
    return "// kernel_dsl: export handled by layerstack exporter\n"


class KernelDSL:
    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        state.clear()
        state["_expr"] = None
        state["_err"] = ""

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio: Optional[dict] = None) -> None:
        expr = str(params.get("kernel_expr", "fract(sin((x*12.9898+y*78.233+seed*0.001)+t)*43758.5453)") or "")
        if state.get("_expr_src") != expr:
            try:
                kc = compile_kernel_expr(expr)
                state["_expr"] = kc.py_fn
                state["_err"] = ""
            except KernelCompileError as e:
                state["_expr"] = None
                state["_err"] = str(e)
            state["_expr_src"] = expr

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        fn = state.get("_expr")
        seed = int(params.get("seed", params.get("pi1", 1337)) or 1337)
        col = params.get("color", (255, 0, 0))
        try:
            r0, g0, b0 = int(col[0]) & 255, int(col[1]) & 255, int(col[2]) & 255
        except Exception:
            r0, g0, b0 = 255, 0, 0

        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)
        is_matrix = mw > 1 and mh > 1 and (mw * mh) == n

        out: List[RGB] = [(0, 0, 0)] * n
        if not callable(fn):
            # Show error as a red "bar" so it's obvious.
            for i in range(min(n, 16)):
                out[i] = (255, 0, 0)
            return out

        for i in range(n):
            if is_matrix:
                x = 0.0 if mw <= 1 else float(i % mw) / float(mw - 1)
                y = 0.0 if mh <= 1 else float(i // mw) / float(mh - 1)
            else:
                x = 0.0 if n <= 1 else float(i) / float(n - 1)
                y = 0.0
            v = float(fn(x, y, float(t), seed))
            if v < 0.0:
                v = 0.0
            if v > 1.0:
                v = 1.0
            out[i] = (int(r0 * v) & 255, int(g0 * v) & 255, int(b0 * v) & 255)
        return out


def register_kernel_dsl() -> None:
    eff = KernelDSL()
    from behaviors.stateful_adapter import AdapterHints, make_stateful_hooks

    preview_emit, update = make_stateful_hooks(eff, hints=AdapterHints(num_leds=60, mw=0, mh=0, fixed_dt=1 / 60))
    defn = BehaviorDef(
        "kernel_dsl",
        title="Kernel DSL",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
