from __future__ import annotations
from app.project_canonical import apply_project_root, apply_project_roots

import time
import json
import hashlib
from typing import Callable, Optional

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from app.project_model import get_surface_snapshot, build_surface_dict


def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )

class DiagnosticsConsoleAuditCompositionMixin:
        def _composition_suite_run_and_check(self) -> tuple[bool, dict]:
            """Atomic composition doors: enabled/blend/order/postfx propagation.

            Deterministic: does NOT depend on time-phase. Mutates project state directly and
            proves Project -> PreviewEngine -> Pixels coherency.
            """
            self._audit_force_heartbeat()
            details = {"checks": []}

            l0 = {"name": "GREEN", "behavior": "solid", "enabled": True, "opacity": 1.0, "blend_mode": "over", "order": 0,
                  "params": {"color": [0, 255, 0]}}
            l1 = {"name": "RED", "behavior": "solid", "enabled": True, "opacity": 1.0, "blend_mode": "over", "order": 1,
                  "params": {"color": [255, 0, 0]}}

            self._audit_inject_project(layers=[l0, l1], rules=[])

            if not self._audit_wait_for_pe_layers(2, 2000):
                return False, {"summary": "PreviewEngine did not expose layers (pe_layers empty)", **details, "state": self._audit_capture_state()}

            def _set_layer(i: int, **fields):
                core = self.app_core
                pm = getattr(core, "pm", None)
                changed = False
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    for k, v in fields.items():
                        try:
                            did = bool(pm.guarded_set_address(f"layers[{int(i)}].{str(k)}", v))
                            changed = did or changed
                            if did:
                                try:
                                    core.project = dict(getattr(pm, "project", {}) or {})
                                except Exception:
                                    pass

                        except Exception:
                            pass
                else:
                    p = dict(core.project)
                    layers = list(p.get("layers", []))
                    if i >= len(layers):
                        return False
                    li = dict(layers[i])
                    for k, v in fields.items():
                        li[k] = v
                    layers[i] = li
                    p2, _validation, _changes = apply_project_root(p, "layers", layers)
                    core.project = p2
                    changed = True
                if changed:
                    self._audit_safe_rebuild("audit_layer_mutation")
                return changed

            def _set_postfx(**fields):
                core = self.app_core
                pm = getattr(core, "pm", None)
                changed = False
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    for k, v in fields.items():
                        try:
                            did = bool(pm.guarded_set_address(f"project.postfx.{str(k)}", v))
                            changed = did or changed
                            if did:
                                try:
                                    core.project = dict(getattr(pm, "project", {}) or {})
                                except Exception:
                                    pass
                        except Exception:
                            pass
                else:
                    p = dict(core.project)
                    postfx = dict(p.get("postfx", {}))
                    for k, v in fields.items():
                        postfx[k] = v
                    p2, _validation, _changes = apply_project_root(p, "postfx", postfx)
                    core.project = p2
                    changed = True
                if changed:
                    self._audit_safe_rebuild("audit_postfx_mutation")

            # T1
            _set_layer(1, enabled=False)
            if not self._audit_wait_for_layer_enabled(1, False, 2000):
                return False, {"summary": "T1/A state timeout: layer1.enabled did not become False", **details, "state": self._audit_capture_state()}
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (0, 255, 0)
            ok = (tuple(st["sample"][0]) == expA)
            details["checks"].append({"id": "T1/A", "expected": list(expA), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T1/A expected GREEN when layer disabled", **details, "state": self._audit_capture_state()}

            _set_layer(1, enabled=True)
            if not self._audit_wait_for_layer_enabled(1, True, 2000):
                return False, {"summary": "T1/B state timeout: layer1.enabled did not become True", **details, "state": self._audit_capture_state()}
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (255, 0, 0)
            ok = (tuple(st["sample"][0]) == expB)
            details["checks"].append({"id": "T1/B", "expected": list(expB), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T1/B expected RED when layer enabled", **details, "state": self._audit_capture_state()}

            # T2
            _set_layer(1, opacity=0.6, blend_mode="over")
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (153, 102, 0)
            ok = (tuple(st["sample"][0]) == expA)
            details["checks"].append({"id": "T2/A", "expected": list(expA), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T2/A expected OVER mix", **details, "state": self._audit_capture_state()}

            _set_layer(1, opacity=0.6, blend_mode="add")
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (153, 255, 0)
            ok = (tuple(st["sample"][0]) == expB)
            details["checks"].append({"id": "T2/B", "expected": list(expB), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T2/B expected ADD mix", **details, "state": self._audit_capture_state()}

            _set_layer(1, opacity=1.0, blend_mode="over")

            # T3
            _set_layer(0, order=0)
            _set_layer(1, order=1)
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (255, 0, 0)
            ok = (tuple(st["sample"][0]) == expA)
            details["checks"].append({"id": "T3/A", "expected": list(expA), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T3/A expected RED on top with ord 0<1", **details, "state": self._audit_capture_state()}

            _set_layer(0, order=1)
            _set_layer(1, order=0)
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (0, 255, 0)
            ok = (tuple(st["sample"][0]) == expB)
            details["checks"].append({"id": "T3/B", "expected": list(expB), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T3/B expected GREEN on top after swap", **details, "state": self._audit_capture_state()}

            _set_layer(0, order=0)
            _set_layer(1, order=1)

            # T4
            _set_layer(1, opacity=0.0)
            _set_postfx(trail_amount=0.0)
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (0, 255, 0)
            ok = (tuple(st["sample"][0]) == expA)
            details["checks"].append({"id": "T4/A", "expected": list(expA), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T4/A expected GREEN with red opacity 0 and trail 0", **details, "state": self._audit_capture_state()}

            # T4/A2: trail OFF should not accumulate history (hash stable across frames)
            h1 = st.get("hash")
            self._audit_wait(120)
            st2 = self._audit_frame_stats(self._audit_render_frame())
            ok2 = (st2.get("hash") == h1)
            details["checks"].append({"id": "T4/A2", "expected": "same_hash", "got": {"h1": h1, "h2": st2.get("hash")}, "ok": ok2})
            if not ok2:
                return False, {"summary": "T4/A2 expected stable hash when trail is OFF", **details, "state": self._audit_capture_state()}

            _set_layer(1, opacity=1.0)
            _set_postfx(trail_amount=0.85)
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (255, 0, 0)
            ok = (tuple(st["sample"][0]) == expB)
            details["checks"].append({"id": "T4/B", "expected": list(expB), "got": st, "ok": ok})
            if not ok:
                return False, {"summary": "T4/B expected RED with trail enabled", **details, "state": self._audit_capture_state()}

            return True, details

        def _run_composition_door_suite(self) -> None:
            """All Doors Open: Composition wiring suite.

            Runs 4 sequential tests, each driven by Rules (tick + time.square1hz/time.square1hz_inv).
            Snapshots are phase-aligned for rock-solid A/B alternation.
            Prints two snapshots per test (A=inv/high, B=square/high), then ends.

            Doors covered:
              T1 enabled
              T2 blend_mode
              T3 order
              T4 project.postfx.trail_amount (with a blinking stimulus so it has a visible effect)
            """
            core = getattr(self, "app_core", None)
            if core is None:
                self._log("[Suite] No app_core")
                return

            # Force wallclock-derived time signals while the suite is running.
            # (PreviewEngine's internal time source may be stalled if nothing is rendering.)
            try:
                setattr(core, "_force_wallclock_signals", True)
            except Exception:
                pass

            # Ensure diagnostics heartbeat (updates time.* signals)
            self._heartbeat_enabled = True
            if not self._hb_timer.isActive():
                self._hb_timer.start(50)  # 20Hz
                self._log("[Heartbeat] started (20Hz).")

            self._log("=== COMPOSITION DOOR SUITE (enabled / blend / order / postfx) ===")
            self._log("Expected: each test prints A then B state with preview sample changing accordingly.")

            self._suite_t0 = time.time()

            # ---- helpers ----
            def _safe_rebuild(reason: str):
                # Prefer core-level rebuild hooks (keeps preview/export parity plumbing consistent)
                for fn_name in ("rebuild_preview", "rebuild_all", "_rebuild_preview"):
                    fn = getattr(core, fn_name, None)
                    if callable(fn):
                        try:
                            fn(reason)
                            return
                        except Exception:
                            pass
                # fallback: poke preview engine
                pe = getattr(core, "preview_engine", None)
                if pe is not None:
                    for fn_name in ("set_project", "rebuild_from_project", "rebuild", "reset"):
                        fn = getattr(pe, fn_name, None)
                        if callable(fn):
                            try:
                                fn(getattr(core, "project", None)) if fn_name in ("set_project", "rebuild_from_project") else fn()
                                return
                            except Exception:
                                pass

            def _extract_pe_layers():
                pe = getattr(core, "preview_engine", None)
                if pe is None:
                    return ({}, {})
                candidates = [
                    getattr(pe, "project", None),
                    getattr(pe, "_project", None),
                    getattr(pe, "project_model", None),
                    getattr(pe, "_project_model", None),
                    getattr(pe, "proj", None),
                ]
                layers = None
                for c in candidates:
                    try:
                        if c is None:
                            continue
                        ls = getattr(c, "layers", None)
                        if isinstance(ls, list) and len(ls) >= 2:
                            layers = ls
                            break
                    except Exception:
                        continue
                if layers is None:
                    # some engines keep layers directly
                    ls = getattr(pe, "layers", None)
                    if isinstance(ls, list) and len(ls) >= 2:
                        layers = ls
                def pack(L):
                    if L is None:
                        return {}
                    if isinstance(L, dict):
                        return {
                            "en": bool(L.get("enabled", True)),
                            "op": float(L.get("opacity", 1.0) if L.get("opacity", None) is not None else 1.0),
                            "bm": str(L.get("blend_mode", "?")),
                            "ord": L.get("order", None),
                        }
                    # object-ish
                    out = {}
                    for k, kk in (("enabled","en"),("opacity","op"),("blend_mode","bm"),("order","ord")):
                        try:
                            v = getattr(L, k)
                            out[kk] = v
                        except Exception:
                            pass
                    return out
                try:
                    return (pack(layers[0]), pack(layers[1])) if layers else ({}, {})
                except Exception:
                    return ({}, {})

            def _render_and_sample():
                pe = getattr(core, "preview_engine", None)
                if pe is None:
                    return (0, None)
                # try to render a frame so _last_frame is current
                for fn_name in ("render_frame", "render", "tick"):
                    fn = getattr(pe, fn_name, None)
                    if callable(fn):
                        try:
                            fn(time.time()) if fn_name == "render_frame" else fn()
                            break
                        except Exception:
                            pass
                pv = getattr(pe, "_last_frame", None)
                if pv is None:
                    return (0, None)
                try:
                    s = set(pv)
                    return (len(s), list(s)[:3])
                except Exception:
                    return (0, None)

            def snap(tag: str):
                # compact snapshot with project + PE layer fields + preview sample
                fired = []
                try:
                    fired = list(getattr(core, "_rules_last_fired_ids", []) or [])
                except Exception:
                    fired = []

                project = getattr(core, "project", {}) or {}

                def _canon_layer(li: int):
                    try:
                        from runtime.resolver import resolve_address
                        return {
                            "en": resolve_address(project=project, address=f"layers[{li}].enabled", default=True).value,
                            "op": resolve_address(project=project, address=f"layers[{li}].opacity", default=1.0).value,
                            "bm": resolve_address(project=project, address=f"layers[{li}].blend_mode", default="over").value,
                            "ord": resolve_address(project=project, address=f"layers[{li}].order", default=None).value,
                        }
                    except Exception:
                        return {
                            "en": True,
                            "op": 1.0,
                            "bm": "over",
                            "ord": None,
                        }

                pe0, pe1 = _extract_pe_layers()
                uniq, sample = _render_and_sample()
                try:
                    from runtime.resolver import resolve_address
                    pfx_tr = resolve_address(project=project, address="project.postfx.trail_amount", default=None).value
                except Exception:
                    pfx_tr = None
                l0 = _canon_layer(0)
                l1 = _canon_layer(1)
                self._log(f"[S] {tag} t+{(time.time()-self._suite_t0):.2f}s fired={fired} preview uniq={uniq} sample={sample}")
                self._log(f"    proj0(en={l0['en']} op={l0['op']} bm={l0['bm']} ord={l0['ord']}) "
                          f"proj1(en={l1['en']} op={l1['op']} bm={l1['bm']} ord={l1['ord']})")
                self._log(f"    pe0={pe0} pe1={pe1}")
                self._log(f"    postfx.trail_amount={pfx_tr}")

            def inject_project(*, layers: list, rules: list, postfx: dict | None = None):
                # keep layout consistent with current project
                p0 = dict(getattr(core, "project", {}) or {})
                surface = get_surface_snapshot(p0)
                if not isinstance(surface, dict) or not surface:
                    surface = build_surface_dict(kind='strip', count=144)

                ui = dict(p0.get("ui") or {}) if isinstance(p0.get("ui"), dict) else {}
                ui["selected_layer"] = 1
                variables = p0.get("variables")
                if not isinstance(variables, dict):
                    variables = {"number": {}, "toggle": {}}
                updates = {
                    "surface": surface,
                    "layers": layers,
                    "ui": ui,
                    "rules": rules,
                    "variables": variables,
                }
                if postfx is not None:
                    updates["postfx"] = dict(postfx)

                p, _validation, _changes = apply_project_roots(p0, updates)
                core.project = p
                core.project_dirty = True
                _safe_rebuild("composition_suite_inject")

            # ---- rule builders (same schema as the working opacity harness) ----
            def r_tick(id_: str, name: str, cond_signal: str, op: str, value: float, action: dict):
                return {
                    "id": id_,
                    "enabled": True,
                    "name": name,
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [{"signal": cond_signal, "op": op, "value": value}],
                    "action": action,
                }

            # suite scheduler
            steps: list[tuple[float, callable]] = []
            t = 0.0
            def add(dt: float, fn):
                nonlocal t
                t += dt
                steps.append((t, fn))

            def run_step(i: int = 0):
                if i >= len(steps):
                    try:
                        setattr(core, "_force_wallclock_signals", False)
                    except Exception:
                        pass
                    self._log("=== END SUITE ===")
                    return
                # steps[] stores *absolute* offsets from suite start; schedule each step
                # against the suite clock (not cumulatively from 'now'), otherwise delays
                # compound and can lock A/B snaps to the same 1Hz phase.
                delay_s, fn = steps[i]
                try:
                    now_rel = float(time.time() - self._suite_t0)
                except Exception:
                    now_rel = 0.0
                wait_s = max(0.0, float(delay_s) - float(now_rel))
                def _invoke_step():
                    try:
                        # If fn accepts a callback, it must call it when the step is truly complete.
                        if getattr(fn, "__code__", None) is not None and fn.__code__.co_argcount >= 1:
                            fn(lambda: run_step(i+1))
                        else:
                            fn()
                            run_step(i+1)
                    except Exception as e:
                        try:
                            self._log(f"[W] Suite step {i} raised: {e}")
                        except Exception:
                            pass
                        run_step(i+1)

                QtCore.QTimer.singleShot(int(wait_s * 1000), _invoke_step)

            # Phase-aligned snapshot helper (prevents A/B landing on the same 1Hz level)
            def snap_on_phase(tag: str, signal_name: str, *, high: bool = True, settle_ms: int = 0,
                              timeout_ms: int = 2500, poll_ms: int = 20, done=None):
                """Wait until signal reaches a stable high/low phase, then snap().

                Uses hard thresholds and requires consecutive polls to avoid edge ambiguity near transitions.
                Calls `done()` after the snapshot has been taken (or on timeout).
                """
                t_start = time.time()

                def _read_sig() -> float:
                    try:
                        v = core.get_signal_value(signal_name)  # type: ignore[attr-defined]
                        return float(v)
                    except Exception:
                        try:
                            return float(core.signals.get(signal_name, 0.0))  # type: ignore[attr-defined]
                        except Exception:
                            return 0.0

                def _finish():
                    if callable(done):
                        try:
                            done()
                        except Exception:
                            pass

                def _do_snap():
                    try:
                        snap(tag)
                    finally:
                        _finish()

                def _tick():
                    v = _read_sig()
                    ok = (v >= 0.9) if high else (v <= 0.1)
                    if ok:
                        _tick.ok_count = getattr(_tick, 'ok_count', 0) + 1  # type: ignore[attr-defined]
                        if _tick.ok_count < 3:  # type: ignore[attr-defined]
                            QtCore.QTimer.singleShot(int(poll_ms), _tick)
                            return
                        if int(settle_ms) > 0:
                            QtCore.QTimer.singleShot(int(settle_ms), _do_snap)
                        else:
                            _do_snap()
                        return
                    else:
                        _tick.ok_count = 0  # type: ignore[attr-defined]

                    if (time.time() - t_start) * 1000.0 >= float(timeout_ms):
                        self._log(f"[W] {tag} phase wait timed out for {signal_name} (v={v:.3f}); snapping anyway")
                        _do_snap()
                        return

                    QtCore.QTimer.singleShot(int(poll_ms), _tick)

                _tick()

            # ---------------- T1: enabled ----------------
            self._log("--- [T1] enabled via Rules ---")
            def t1_inject():
                ts = int(time.time() * 1000)
                layers = [
                    {"uid": f"t1_{ts}_0", "name":"BASE GREEN", "behavior":"solid",                      "params":{"color":[0,255,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":0},
                    {"uid": f"t1_{ts}_1", "name":"OVER RED", "behavior":"solid",                      "params":{"color":[255,0,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":1},
                ]
                rules = [
                    r_tick("t1_off", "Red disabled while square1hz_inv", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"enabled","expr":{"src":"const","const":0}}),
                    r_tick("t1_on", "Red enabled while square1hz", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"enabled","expr":{"src":"const","const":1}}),
                ]
                inject_project(layers=layers, rules=rules)

            add(0.00, t1_inject)
            # Phase-align snapshots so A/B always differ (rock solid)
            add(0.20, lambda done=None: snap_on_phase("T1/A", "time.square1hz_inv", high=True, done=done))
            add(2.20, lambda done=None: snap_on_phase("T1/B", "time.square1hz", high=True, done=done))

            # ---------------- T2: blend_mode ----------------
            self._log("--- [T2] blend_mode via Rules ---")
            def t2_inject():
                ts = int(time.time() * 1000)
                layers = [
                    {"uid": f"t2_{ts}_0", "name":"BASE GREEN", "behavior":"solid",                      "params":{"color":[0,255,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":0},
                    {"uid": f"t2_{ts}_1", "name":"OVER RED 0.6", "behavior":"solid",                      "params":{"color":[255,0,0]}, "opacity":0.6, "enabled":True, "blend_mode":"over", "order":1},
                ]
                rules = [
                    r_tick("t2_norm", "Blend over while inv", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"blend_mode","expr":{"src":"const","const":"over"}}),
                    r_tick("t2_add", "Blend add while square", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"blend_mode","expr":{"src":"const","const":"add"}}),
                ]
                inject_project(layers=layers, rules=rules)

            add(0.30, t2_inject)
            # Phase-align snapshots so A/B always differ (rock solid)
            add(0.20, lambda done=None: snap_on_phase("T2/A", "time.square1hz_inv", high=True, done=done))
            add(2.20, lambda done=None: snap_on_phase("T2/B", "time.square1hz", high=True, done=done))

            # ---------------- T3: order ----------------
            self._log("--- [T3] order via Rules ---")
            def t3_inject():
                ts = int(time.time() * 1000)
                layers = [
                    {"uid": f"t3_{ts}_0", "name":"GREEN", "behavior":"solid",                      "params":{"color":[0,255,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":0},
                    {"uid": f"t3_{ts}_1", "name":"RED", "behavior":"solid",                      "params":{"color":[255,0,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":1},
                ]
                rules = [
                    # INV: red on top
                    r_tick("t3_inv_l0", "Order INV l0=0", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":0,"param":"order","expr":{"src":"const","const":0}}),
                    r_tick("t3_inv_l1", "Order INV l1=1", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"order","expr":{"src":"const","const":1}}),
                    # SQ: green on top (swap)
                    r_tick("t3_sq_l0", "Order SQ l0=1", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":0,"param":"order","expr":{"src":"const","const":1}}),
                    r_tick("t3_sq_l1", "Order SQ l1=0", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"order","expr":{"src":"const","const":0}}),
                ]
                inject_project(layers=layers, rules=rules)

            add(0.30, t3_inject)
            # Important: phase-align, otherwise both snaps can land on the same 1Hz level.
            add(0.20, lambda done=None: snap_on_phase("T3/A", "time.square1hz_inv", high=True, done=done))
            add(1.20, lambda done=None: snap_on_phase("T3/B", "time.square1hz", high=True, done=done))

            # ---------------- T4: postfx trail_amount (visible) ----------------
            self._log("--- [T4] project.postfx.trail_amount via Rules ---")
            def t4_inject():
                ts = int(time.time() * 1000)
                layers = [
                    {"uid": f"t4_{ts}_0", "name":"BASE BLACK", "behavior":"solid",                      "params":{"color":[0,0,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":0},
                    {"uid": f"t4_{ts}_1", "name":"RED BLINK", "behavior":"solid",                      "params":{"color":[255,0,0]}, "opacity":1.0, "enabled":True, "blend_mode":"over", "order":1},
                ]
                rules = [
                    # blink red layer via opacity (already proven working)
                    r_tick("t4_red_on", "Red ON while square", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"opacity","expr":{"src":"const","const":1.0}}),
                    r_tick("t4_red_off", "Red OFF while inv", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":1,"param":"opacity","expr":{"src":"const","const":0.0}}),
                    # toggle postfx trail amount
                    r_tick("t4_trail_off", "Trail OFF while inv", "time.square1hz_inv", ">", 0.5,
                           {"kind":"set_layer_param","layer":0,"param":"project.postfx.trail_amount","expr":{"src":"const","const":0.0}}),
                    r_tick("t4_trail_on", "Trail ON while square", "time.square1hz", ">", 0.5,
                           {"kind":"set_layer_param","layer":0,"param":"project.postfx.trail_amount","expr":{"src":"const","const":0.85}}),
                ]
                inject_project(layers=layers, rules=rules, postfx={"trail_amount": 0.0, "bleed_amount": 0.0, "bleed_radius": 2.0})

            add(0.30, t4_inject)
            add(0.30, lambda done=None: snap_on_phase("T4/A", "time.square1hz_inv", high=True, done=done))
            add(1.40, lambda done=None: snap_on_phase("T4/B", "time.square1hz", high=True, done=done))

            # Kick off
            run_step(0)
