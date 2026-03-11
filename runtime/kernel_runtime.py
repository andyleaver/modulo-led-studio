from __future__ import annotations

"""
runtime.kernel_runtime

First-class programmable kernel runtime for preview.

Goals:
- Compile-on-change (per-layer cache, keyed by source hash)
- Stable ctx API (KernelContext)
- Mapping truth via surface['coords'] when available
- No silent failure: status + diagnostics + visible fallback color
- Safe sandbox + import whitelist
- Budget watchdog (time-based)

Export parity: this module is the preview runtime. Export uses the kernel DSL or target-side code injection as declared by the exporter.
"""

import hashlib
import time
from typing import Any, Dict, Optional, Callable, Tuple, List

from runtime.kernel_context import KernelContext, KernelRNG
from runtime.kernel_status import KernelStatus
from runtime.diagnostics import GLOBAL_DIAGS

RGB = Tuple[int,int,int]

_ALLOWED_IMPORTS = ("math","random")

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in _ALLOWED_IMPORTS:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"kernel import blocked: {name}")

def _make_sandbox_globals() -> Dict[str, Any]:
    import math, random
    safe_builtins = {
        "min": min, "max": max, "abs": abs, "int": int, "float": float, "range": range, "round": round,
        "len": len, "sum": sum, "enumerate": enumerate, "list": list, "dict": dict, "set": set, "tuple": tuple,
        "sorted": sorted, "pow": pow, "__import__": _safe_import,
    }
    return {"__builtins__": safe_builtins, "math": math, "random": random}

def _sha12(src: str) -> str:
    return hashlib.sha256(src.encode("utf-8", errors="ignore")).hexdigest()[:12]

def _coerce_rgb(out: Any) -> RGB:
    try:
        if isinstance(out, (list, tuple)) and len(out) >= 3:
            r,g,b = out[0], out[1], out[2]
            # float 0..1
            if isinstance(r, float) or isinstance(g, float) or isinstance(b, float):
                r = int(max(0, min(255, round(float(r)*255.0))))
                g = int(max(0, min(255, round(float(g)*255.0))))
                b = int(max(0, min(255, round(float(b)*255.0))))
            else:
                r = int(max(0, min(255, int(r))))
                g = int(max(0, min(255, int(g))))
                b = int(max(0, min(255, int(b))))
            return (r,g,b)
    except Exception:
        pass
    return (0,0,0)

def _norm_coords(surface: Optional[Dict[str,Any]], n: int) -> Optional[List[Tuple[float,float]]]:
    if not isinstance(surface, dict):
        return None
    coords = surface.get("coords")
    if not (isinstance(coords, list) and len(coords) == int(n) and n > 0):
        return None
    # compute bounds in source coord space
    xs=[]; ys=[]
    for c in coords:
        if isinstance(c,(list,tuple)) and len(c)>=2:
            try:
                xs.append(float(c[0])); ys.append(float(c[1]))
            except Exception:
                pass
    if not xs or not ys:
        return None
    xmin,xmax=min(xs),max(xs)
    ymin,ymax=min(ys),max(ys)
    dx=(xmax-xmin) if (xmax-xmin)!=0 else 1.0
    dy=(ymax-ymin) if (ymax-ymin)!=0 else 1.0
    out=[]
    for c in coords:
        if isinstance(c,(list,tuple)) and len(c)>=2:
            x=(float(c[0])-xmin)/dx
            y=(float(c[1])-ymin)/dy
        else:
            x=y=0.0
        out.append((x,y))
    return out

class _CompiledKernel:
    def __init__(self, src: str):
        self.src = src
        self.hash = _sha12(src)
        self.g: Optional[Dict[str,Any]] = None
        self.l: Optional[Dict[str,Any]] = None
        self.init_fn: Optional[Callable[[KernelContext], Any]] = None
        self.update_fn: Optional[Callable[[KernelContext], Any]] = None
        self.pixel_fn: Optional[Callable[..., Any]] = None
        self.mode: str = ""  # "ctx" or "legacy"

    def compile(self) -> None:
        g = _make_sandbox_globals()
        l: Dict[str,Any] = {}
        code = compile(self.src, f"kernel_{self.hash}", "exec")
        exec(code, g, l)
        # functions may be in locals or globals (depends on exec behavior)
        init_fn = l.get("init") or g.get("init")
        update_fn = l.get("update") or g.get("update")
        pixel_fn = l.get("pixel") or g.get("pixel")
        if not callable(pixel_fn):
            raise ValueError("kernel must define callable pixel(...)")
        self.init_fn = init_fn if callable(init_fn) else None
        self.update_fn = update_fn if callable(update_fn) else None
        self.pixel_fn = pixel_fn
        # detect signature style
        # prefer ctx: pixel(ctx)
        try:
            import inspect
            sig = inspect.signature(pixel_fn)
            params = list(sig.parameters.values())
            self.mode = "ctx" if len(params) >= 1 else "legacy"
        except Exception:
            self.mode = "ctx"
        self.g, self.l = g, l

class KernelRuntime:
    def __init__(self):
        pass

    def ensure_compiled(self, *, state: Dict[str,Any], source: str, status: KernelStatus) -> Optional[_CompiledKernel]:
        src = (source or "").strip()
        h = _sha12(src)
        status.source_hash = h
        cache = state.setdefault("_kernel_cache", {})
        if not isinstance(cache, dict):
            cache = {}
            state["_kernel_cache"] = cache
        ck = cache.get(h)
        if not isinstance(ck, _CompiledKernel):
            ck = _CompiledKernel(src)
            cache[h] = ck
        # reuse if already compiled successfully
        if state.get("_kernel_compiled_hash") == h and status.last_compile_ok and ck.pixel_fn:
            return ck
        # compile
        try:
            ck.compile()
            status.compile_count += 1
            status.last_compile_ok = True
            status.last_compile_error = None
            status.state = "OK"
            state["_kernel_compiled_hash"] = h
            state["_kernel_module_hash"] = h
            # init hook on (re)compile
            if ck.init_fn:
                ctx = state.get("_kernel_ctx")
                if not isinstance(ctx, KernelContext):
                    ctx = KernelContext()
                    state["_kernel_ctx"] = ctx
                ck.init_fn(ctx)
                state["_kernel_inited_hash"] = h
            return ck
        except Exception as e:
            status.compile_count += 1
            status.last_compile_ok = False
            status.last_compile_error = f"{type(e).__name__}: {e}"
            status.state = "COMPILE_FAILED"
            if GLOBAL_DIAGS is not None:
                GLOBAL_DIAGS.exception(e, domain="KERNEL", code="KERNEL_COMPILE_FAILED", summary=str(e), layer_id=layer_id, layer_name=layer_name, behavior_id=behavior_id, project_id=project_id, app_id=app_id, correlation_id=correlation_id, details={"source_hash": h})
            return None

    def reset_kernel(self, state: Dict[str,Any], status: KernelStatus, *, full: bool=True) -> None:
        # full reset clears vars + cache + ctx
        if full:
            state.pop("_kernel_cache", None)
            state.pop("_kernel_compiled_hash", None)
            state.pop("_kernel_inited_hash", None)
            state.pop("_kernel_ctx", None)
        # vars reset
        vars0 = state.setdefault("vars", {})
        if isinstance(vars0, dict):
            vars0.clear()
        status.strikes = 0
        status.error_count = 0
        status.last_error = None
        status.last_error_frame = None
        status.state = "IDLE"

    def run_preview(self, *, num_leds: int, surface: Optional[Dict[str,Any]], params: Dict[str,Any],
                    t: float, dt: float, frame: int, state: Dict[str,Any], audio: Optional[Dict[str,Any]],
                    status: KernelStatus, source: str,
                    layer_id: Optional[str]=None, layer_name: Optional[str]=None, behavior_id: Optional[str]=None,
                    project_id: Optional[str]=None, app_id: Optional[str]=None, correlation_id: Optional[str]=None) -> List[RGB]:
        # disabled?
        if status.state == "DISABLED":
            return [(0,0,0)] * int(num_leds)
        # explicit reset token
        reset_token = params.get("reset_token") if isinstance(params, dict) else None
        if reset_token is not None and reset_token != state.get("_kernel_reset_token"):
            state["_kernel_reset_token"] = reset_token
            self.reset_kernel(state, status, full=True)

        # explicit vars-only reset token (clears ctx.vars without recompiling)
        vars_reset_token = params.get("vars_reset_token") if isinstance(params, dict) else None
        if vars_reset_token is not None and vars_reset_token != state.get("_kernel_vars_reset_token"):
            state["_kernel_vars_reset_token"] = vars_reset_token
            self.reset_kernel(state, status, full=False)

        ck = self.ensure_compiled(state=state, source=source, status=status)
        if ck is None:
            # compile failed: visible diagnostic magenta
            return [(255,0,255)] * int(num_leds)

        # counters
        counters = status.counters if isinstance(status.counters, dict) else {}
        counters.setdefault("init_called", 0)
        counters.setdefault("update_called", 0)
        counters.setdefault("pixel_called", 0)
        counters.setdefault("budget_exceeded", 0)
        status.counters = counters

        # ctx setup
        ctx = state.get("_kernel_ctx")
        if not isinstance(ctx, KernelContext):
            ctx = KernelContext()
            state["_kernel_ctx"] = ctx
        ctx.t = float(t); ctx.dt = float(dt); ctx.frame = int(frame)
        ctx.params = params if isinstance(params, dict) else {}
        ctx.vars = state.setdefault("vars", {}) if isinstance(state.get("vars", {}), dict) else {}
        seed = int((params or {}).get("seed", 1337) or 1337) if isinstance(params, dict) else 1337
        ctx.seed = seed
        # determinism toggle
        deterministic = bool((params or {}).get("deterministic", True)) if isinstance(params, dict) else True
        ctx.deterministic = deterministic
        if deterministic:
            ctx.rng = KernelRNG(seed ^ 0x9E3779B9)
        else:
            # explicit non-deterministic mode (still seeded, but perturbed by time + frame)
            ctx.rng = KernelRNG((seed ^ (int(frame) & 0xFFFFFFFF) ^ (int(time.time_ns()) & 0xFFFFFFFF)) & 0xFFFFFFFF)
        ctx.audio = audio if isinstance(audio, dict) else None
        ctx.num_leds = int(num_leds)
        ctx.surface = surface if isinstance(surface, dict) else None
        coords01 = _norm_coords(surface, int(num_leds))
        ctx.coords = coords01

        # init hook accounting
        if ck.init_fn and state.get("_kernel_inited_hash") == status.source_hash:
            counters["init_called"] = 1

        start = time.perf_counter()
        try:
            if ck.update_fn:
                ck.update_fn(ctx)
            counters["update_called"] += 1
        except Exception as e:
            status.error_count += 1
            status.last_error = f"{type(e).__name__}: {e}"
            status.last_error_frame = int(frame)
            status.state = "RUNTIME_ERROR"
            if GLOBAL_DIAGS is not None:
                GLOBAL_DIAGS.exception(e, domain="KERNEL", code="KERNEL_UPDATE_ERROR", summary=str(e), layer_id=layer_id, layer_name=layer_name, behavior_id=behavior_id, project_id=project_id, app_id=app_id, correlation_id=correlation_id)
            return [(255,0,255)] * int(num_leds)

        out: List[RGB] = []
        # allow param overrides, but clamp to safe bounds
        budget_ms = float((params or {}).get("budget_ms", status.budget_ms) or 10.0) if isinstance(params, dict) else float(status.budget_ms or 10.0)
        budget_ms = max(0.5, min(200.0, budget_ms))
        strike_limit = int((params or {}).get("strike_limit", status.strike_limit) or 0) if isinstance(params, dict) else int(status.strike_limit or 0)
        status.budget_ms = budget_ms
        status.strike_limit = strike_limit
        for i in range(int(num_leds)):
            # watchdog
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if elapsed_ms > budget_ms:
                status.state = "BUDGET_EXCEEDED"
                status.strikes += 1
                counters["budget_exceeded"] += 1
                status.last_budget_event = f"budget exceeded: {elapsed_ms:.2f}ms > {budget_ms:.2f}ms at i={i}"
                GLOBAL_DIAGS.message(level="WARN", domain="KERNEL", code="KERNEL_BUDGET_EXCEEDED",
                                    summary="Kernel budget exceeded", frame=int(frame),
                                    details={"budget_ms": budget_ms, "elapsed_ms": float(elapsed_ms), "i": int(i), "strikes": int(status.strikes)})
                # auto-disable on strikes
                if strike_limit > 0 and status.strikes >= strike_limit:
                    status.state = "DISABLED"
                    status.disabled_reason = "budget"
                # visible fallback: magenta
                # fill rest with magenta so users SEE it
                out.extend([(255,0,255)] * (int(num_leds) - i))
                return out
            try:
                ctx.i = i
                if coords01 and i < len(coords01):
                    ctx.x, ctx.y = coords01[i]
                else:
                    ctx.x = 0.0 if num_leds <= 1 else float(i) / float(max(1,int(num_leds)-1))
                    ctx.y = 0.0
                if ck.mode == "ctx":
                    px = ck.pixel_fn(ctx)
                else:
                    # legacy compatibility
                    px = ck.pixel_fn(i, ctx.x, ctx.y, ctx.t, ctx.dt, seed, ctx.params, ctx.audio, ctx.vars)
                counters["pixel_called"] += 1
                out.append(_coerce_rgb(px))
            except Exception as e:
                status.error_count += 1
                status.last_error = f"{type(e).__name__}: {e}"
                status.last_error_frame = int(frame)
                status.state = "RUNTIME_ERROR"
                if GLOBAL_DIAGS is not None:
                    GLOBAL_DIAGS.exception(e, domain="KERNEL", code="KERNEL_PIXEL_ERROR", summary=str(e), layer_id=layer_id, layer_name=layer_name, behavior_id=behavior_id, project_id=project_id, app_id=app_id, correlation_id=correlation_id)
                out.append((255,0,255))
        # success
        status.state = "OK"
        return out
