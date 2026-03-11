from __future__ import annotations

import json
import hashlib
import time
from typing import Callable, Optional

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from app.project_model import get_surface_snapshot


class DiagnosticsConsoleAuditStateMixin:
    def _audit_capture_state(self) -> dict:
        """Capture minimal state needed to debug audit failures (shown in Diagnostics evidence)."""
        out = {"proj_layers": [], "pe_layers": [], "fired": [], "pe_meta": {"present": False, "type": None, "last_error": None}, "render_layers": [], "render_path": None, "render_source": None, "render_layer_keys": [], "blend_trace": [], "pe_params": []}
        try:
            out["fired"] = list(getattr(self.app_core, "_rules_last_fired_ids", []) or [])
        except Exception:
            out["fired"] = []

        # Project dict layers (prefer canonical resolver reads for first-class layer fields)
        try:
            p = getattr(self.app_core, "project", {}) or {}
            ls = list(p.get("layers") or [])
            resolver = getattr(self.app_core, "resolve_layer_canonical", None)
            for li, layer in enumerate(ls[:4]):
                if not isinstance(layer, dict):
                    continue
                params = layer.get("params") if isinstance(layer.get("params"), dict) else {}

                def _canon(field: str, default=None):
                    try:
                        if callable(resolver):
                            rr = resolver(li, field, default)
                            return getattr(rr, "value", default)
                    except Exception:
                        pass
                    return default

                out["proj_layers"].append({
                    "i": li,
                    "name": layer.get("name"),
                    "enabled": _canon("enabled", True),
                    "opacity": _canon("opacity", 1.0),
                    "blend_mode": _canon("blend_mode", "over"),
                    "order": _canon("order", li),
                    "behavior": str(layer.get("behavior") or "").strip() or None,
                    "color": params.get("color"),
                    "params_keys": sorted(list(params.keys()))[:12],
                })
        except Exception:
            pass

        # PreviewEngine layers (canonical: prefer _full_preview_engine, fall back to preview_engine)
        try:
            core = self.app_core
            pe = getattr(core, "_full_preview_engine", None) or getattr(core, "preview_engine", None)
            out["pe_meta"] = {
                "present": bool(pe is not None),
                "type": type(pe).__name__ if pe is not None else None,
                "last_error": getattr(core, "_full_preview_last_error", None),
            }
            pm = getattr(pe, "project", None) if pe is not None else None
            pls = list(getattr(pm, "layers", []) or []) if pm is not None else []
            for li, layer in enumerate(pls[:4]):
                try:
                    out["pe_layers"].append({
                        "i": li,
                        "en": getattr(layer, "en", getattr(layer, "enabled", None)),
                        "op": getattr(layer, "op", getattr(layer, "opacity", None)),
                        "bm": getattr(layer, "bm", getattr(layer, "blend_mode", None)),
                        "ord": getattr(layer, "ord", getattr(layer, "order", None)),
                    })
                    # Snapshot params for debugging (helps detect default-color fallbacks).
                    p = getattr(layer, "params", None)
                    if isinstance(p, dict):
                        out["pe_params"].append({"i": li, "keys": sorted(list(p.keys()))[:12], "color": p.get("color")})
                except Exception:
                    continue

            # Optional compositor trace (captured when _debug_blend_trace is enabled).
            try:
                tr = getattr(pe, "_debug_last_trace", None)
                if isinstance(tr, list):
                    out["blend_trace"] = tr[:8]
            except Exception:
                pass
        except Exception:
            out["pe_meta"] = {"present": False, "type": None, "last_error": None}



        # Render/compositor truth (best-effort): capture the actual layer list the renderer is iterating
        try:
            core = self.app_core
            pe = getattr(core, "_full_preview_engine", None) or getattr(core, "preview_engine", None)
            rs = self._audit_capture_render_layers(pe)
            out["render_layers"] = rs.get("layers", []) or []
            out["render_path"] = rs.get("path")
            out["render_source"] = rs.get("source")
            out["render_layer_keys"] = rs.get("layer_keys", []) or []
        except Exception:
            pass

        return out



    def _audit_capture_render_layers(self, pe) -> dict:
        """
        Best-effort introspection of the *actual* layer list used by the preview renderer/compositor.
        Returns: {"source": str|None, "path": str|None, "layers": [dict], "layer_keys": [list[str]]}
        """
        out = {"source": None, "path": None, "layers": [], "layer_keys": []}
        if pe is None:
            return out

        # Try to infer last render path if the engine records it.
        for attr in ("_last_render_path", "last_render_path", "_render_path", "render_path"):
            try:
                v = getattr(pe, attr, None)
                if isinstance(v, str) and v:
                    out["path"] = v
                    break
            except Exception:
                pass

        # Candidate layer containers (ordered by likelihood)
        candidates = [
            ("pe._render_layers", lambda: getattr(pe, "_render_layers", None)),
            ("pe.render_layers", lambda: getattr(pe, "render_layers", None)),
            ("pe._compiled_layers", lambda: getattr(pe, "_compiled_layers", None)),
            ("pe.compiled_layers", lambda: getattr(pe, "compiled_layers", None)),
            ("pe._layers", lambda: getattr(pe, "_layers", None)),
            ("pe.layers", lambda: getattr(pe, "layers", None)),
        ]

        # Sometimes the render loop pulls from pe.project.layers (already captured separately),
        # but we include it here to detect divergence.
        try:
            pm = getattr(pe, "project", None)
            candidates.append(("pe.project.layers", lambda: getattr(pm, "layers", None) if pm is not None else None))
        except Exception:
            pass

        layers_obj = None
        for name, getter in candidates:
            try:
                v = getter()
                if isinstance(v, (list, tuple)) and len(v) > 0:
                    layers_obj = list(v)
                    out["source"] = name
                    break
            except Exception:
                continue

        if layers_obj is None:
            # No obvious list found; return empty but keep source/path.
            return out

        # Capture a small, stable snapshot of each layer-like object
        for i, L in enumerate(layers_obj[:6]):
            try:
                # collect keys for debugging (first two only to limit noise)
                if i < 2:
                    keys = []
                    if isinstance(L, dict):
                        keys = sorted(list(L.keys()))[:40]
                    else:
                        keys = sorted([k for k in dir(L) if not k.startswith("_")])[:60]
                    out["layer_keys"].append(keys)

                def g(attr, default=None):
                    if isinstance(L, dict):
                        return L.get(attr, default)
                    return getattr(L, attr, default)

                snap = {
                    "i": i,
                    "en": g("en", g("enabled", None)),
                    "op": g("op", g("opacity", None)),
                    "bm": g("bm", g("blend_mode", None)),
                    "ord": g("ord", g("order", None)),
                }
                # Report any legacy mirror params still present on the layer.
                try:
                    params = g("params", None)
                    if isinstance(params, dict):
                        found = [k for k in _legacy_layer_param_mirror_keys() if k in params]
                        if found:
                            snap["param_mirrors"] = found
                except Exception:
                    pass

                out["layers"].append(snap)
            except Exception:
                continue

        return out
    def _audit_force_heartbeat(self) -> None:
        try:
            setattr(self.app_core, "_force_wallclock_signals", True)
        except Exception:
            pass
        self._heartbeat_enabled = True
        if not self._hb_timer.isActive():
            self._hb_timer.start(50)  # 20Hz
            self._log("[Heartbeat] started (20Hz).")

    def _audit_safe_rebuild(self, reason: str) -> None:
        core = self.app_core
        for fn_name in ("rebuild_preview", "rebuild_all", "_rebuild_preview"):
            fn = getattr(core, fn_name, None)
            if callable(fn):
                try:
                    fn(reason)
                    return
                except Exception:
                    pass
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

    def _audit_render_frame(self):
        # Prefer the legacy preview_engine for diagnostics. It is deterministic and avoids
        # UI-thread stalls that can happen with the full renderer when driven in tight loops.
        core = self.app_core
        pe = getattr(core, "_full_preview_engine", None) or getattr(core, "preview_engine", None)
        if pe is None:
            return None
        # Enable optional per-layer blend trace if supported by this PreviewEngine build.
        try:
            setattr(pe, "_debug_blend_trace", True)
        except Exception:
            pass
        # Guard render calls: some engines can stall under certain combinations of
        # postfx + rebuild + rapid stepping. If a render call doesn't return quickly,
        # fall back to the last known frame so the audit can finish and report.
        def _call_with_timeout(func, args=(), kwargs=None, timeout_s: float = 0.5):
            import threading
            out = {"ok": False, "exc": None}
            if kwargs is None:
                kwargs = {}
            def _runner():
                try:
                    func(*args, **kwargs)
                    out["ok"] = True
                except Exception as e:
                    out["exc"] = e
            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join(timeout_s)
            return out["ok"], out["exc"], t.is_alive()

        for fn_name in ("render_frame", "render", "tick"):
            fn = getattr(pe, fn_name, None)
            if callable(fn):
                try:
                    if fn_name == "render_frame":
                        ok, exc, alive = _call_with_timeout(fn, args=(time.time(),), timeout_s=0.5)
                        if alive:
                            self._log("[Audit] WARN: render_frame timeout; using last_frame")
                            break
                        if (not ok) and exc is not None:
                            # swallow and continue; we may still have a last_frame
                            pass
                    else:
                        ok, exc, alive = _call_with_timeout(fn, timeout_s=0.5)
                        if alive:
                            self._log(f"[Audit] WARN: {fn_name} timeout; using last_frame")
                            break
                        if (not ok) and exc is not None:
                            pass
                    break
                except Exception:
                    pass
        return getattr(pe, "_last_frame", None)

    def _audit_frame_stats(self, frame):
        if not frame:
            return {"uniq": 0, "sample": None, "hash": None}
        try:
            s = set(frame)
            sample = list(s)[:3]
            try:
                import hashlib as _hashlib
                h = _hashlib.md5(repr(frame).encode("utf-8")).hexdigest()[:10]
            except Exception:
                h = None
            return {"uniq": len(s), "sample": sample, "hash": h}
        except Exception:
            return {"uniq": 0, "sample": None, "hash": None}

