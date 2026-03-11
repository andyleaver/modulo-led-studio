from __future__ import annotations

import time
import json

from qt.diagnostics_console_doors_probe_support import legacy_layer_param_mirror_keys


class DiagnosticsConsoleDoorsOverrideProbesMixin:
    def _probe_operator_overrides(self) -> str:
        """Door F1: Operator overrides (preview)

        Proves that operator overrides written by Rules via canonical addresses
        (operator.gain -> layers[i]._op_overrides.gain) are consumed by
        PreviewEngine's operator pipeline.

        PREVIEW-only (export parity is a later door).
        """
        core = self.app_core

        def sample_pixel0(frame):
            try:
                if not frame:
                    return (None, None, None)
                p = frame[0]
                if isinstance(p, (list, tuple)) and len(p) >= 3:
                    return (int(p[0]) & 255, int(p[1]) & 255, int(p[2]) & 255)
                if isinstance(p, int):
                    return ((p >> 16) & 255, (p >> 8) & 255, p & 255)
            except Exception:
                pass
            return (None, None, None)

        layers = [
            {
                "name": "SOLID GREY + GAIN",
                "behavior": "solid",
                "params": {"color": [80, 80, 80]},
                "opacity": 1.0,
                "enabled": True,
                "blend_mode": "over",
                "order": 0,
                # IMPORTANT: project_normalize enforces operators[0].type == behavior.
                # So we include the behavior op in slot 0 and the gain operator in slot 1.
                "operators": [
                    {"type": "solid", "enabled": True, "params": {}},
                    {"type": "gain", "enabled": True, "params": {"gain": 1.0}},
                ],
            }
        ]

        rules = [
            {
                "id": "r_gain_hi",
                "enabled": True,
                "name": "GAIN=2 while square1hz",
                "trigger": "tick",
                "trigger_mode": "all",
                "conditions": [{"signal": "time.square1hz", "op": ">", "value": 0.5}],
                "action": {"kind": "set_layer_param", "layer": 0, "param": "operator.gain",
                           "expr": {"src": "const", "const": 2.0}},
            },
            {
                "id": "r_gain_lo",
                "enabled": True,
                "name": "GAIN=1 while square1hz_inv",
                "trigger": "tick",
                "trigger_mode": "all",
                "conditions": [{"signal": "time.square1hz_inv", "op": ">", "value": 0.5}],
                "action": {"kind": "set_layer_param", "layer": 0, "param": "operator.gain",
                           "expr": {"src": "const", "const": 1.0}},
            },
        ]

        try:
            self._audit_inject_project(layers=layers, rules=rules, postfx=None)
        except Exception as e:
            return f"[OpOverrides] ERROR: inject failed ({type(e).__name__})"

        tick_fn = getattr(core, "_update_signals_from_preview", None)
        if not callable(tick_fn):
            return "[OpOverrides] FAIL: missing CoreBridge._update_signals_from_preview (cannot evaluate rules)"

        ev = {"rules": {}}
        pixel_changes = []
        saw_gain1 = False
        saw_gain2 = False
        fired_any = False
        last_fired = []
        last_errors = []
        time_sq = None

        for _ in range(48):  # ~2.4s at 20Hz
            now = time.time()
            try:
                tick_fn(now)
            except Exception:
                pass

            try:
                from runtime.resolver import resolve_address
                pr = getattr(core, "project", {}) or {}
                gain_res = resolve_address(project=pr, address="layers[0]._op_overrides.gain")
                g = getattr(gain_res, "value", None)
                if g == 1.0:
                    saw_gain1 = True
                if g == 2.0:
                    saw_gain2 = True
            except Exception:
                pass

            try:
                lf = list(getattr(core, "_rules_last_fired_ids", []) or [])
                le = list(getattr(core, "_rules_last_errors", []) or [])
                if lf:
                    fired_any = True
                last_fired = lf
                last_errors = le
            except Exception:
                pass

            try:
                sigs = getattr(core, "_last_signals", None)
                if isinstance(sigs, dict):
                    time_sq = float(sigs.get("time.square1hz", time_sq) or time_sq or 0.0)
            except Exception:
                pass

            try:
                self._audit_safe_rebuild("door_f1_tick")
            except Exception:
                pass
            frame = self._audit_render_frame()
            px = sample_pixel0(frame)
            pixel_changes.append(px)
            # Do not block the UI thread; keep Qt responsive.
            self._audit_wait(50)

        if len(pixel_changes) <= 12:
            trimmed = pixel_changes
        else:
            trimmed = pixel_changes[:6] + ["..."] + pixel_changes[-6:]

        ev["rules"] = {
            "pixel_changes": trimmed,
            "saw_gain2": bool(saw_gain2),
            "saw_gain1": bool(saw_gain1),
            "fired_any": bool(fired_any),
            "last_fired": last_fired,
            "last_errors": last_errors,
            "time_square1hz": time_sq,
        }

        uniq = set([p for p in pixel_changes if isinstance(p, tuple)])
        if (80, 80, 80) in uniq and (160, 160, 160) in uniq:
            return "[OpOverrides] PASS"

        if len(uniq) == 0 or all((p[0] is None) for p in uniq):
            return "[OpOverrides] FAIL: could not sample preview pixels " + json.dumps(ev, separators=(',',':'))

        return "[OpOverrides] FAIL: did not observe gain affecting output " + json.dumps(ev, separators=(',',':'))


    def _probe_override_priority(self) -> str:
            """Door J1: Override priority (Rules/runtime mutations win over authored baseline).

            Deterministic, probe-only.

            PASS condition:
            - We observe BOTH 0.75 and 0.25 applied to layers[0].opacity (canonical)
              across a controlled time-stepped run.

            Notes:
            - Does not mutate the layer dict directly (no 'fight' writes).
            - Uses audit stepping and safe rebuild to avoid coupling/races with other doors.
            """
            core = getattr(self, "app_core", None)
            if core is None:
                return "[OverridePriority] ERROR: no app_core"

            layers = [
                {
                    "name": "OPACITY PRIORITY HARNESS",
                    "behavior": "solid",
                    "params": {"color": [80, 80, 80], "opacity": 0.10},
                    "opacity": 0.10,
                    "enabled": True,
                    "blend_mode": "over",
                    "order": 0,
                    "operators": [{"type": "solid", "enabled": True, "params": {}}],
                }
            ]

            rules = [
                {
                    "id": "r_op_hi",
                    "enabled": True,
                    "name": "opacity=0.75 while square1hz",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [{"signal": "time.square1hz", "op": ">", "value": 0.5}],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "opacity",
                               "expr": {"src": "const", "const": 0.75}},
                },
                {
                    "id": "r_op_lo",
                    "enabled": True,
                    "name": "opacity=0.25 while square1hz_inv",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [{"signal": "time.square1hz_inv", "op": ">", "value": 0.5}],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "opacity",
                               "expr": {"src": "const", "const": 0.25}},
                },
            ]

            try:
                self._audit_inject_project(layers=layers, rules=rules, postfx=None)
                self._audit_safe_rebuild("door_j1_inject")
            except Exception as e:
                return f"[OverridePriority] ERROR: inject failed ({type(e).__name__})"

            tick_fn = getattr(core, "_update_signals_from_preview", None)
            if not callable(tick_fn):
                return "[OverridePriority] ERROR: core has no _update_signals_from_preview(t)"

            old_force = getattr(core, "_force_wallclock_signals", None)
            try:
                setattr(core, "_force_wallclock_signals", True)
            except Exception:
                old_force = None

            def get_layer():
                try:
                    p = getattr(core, "project", None) or {}
                    layers_ = p.get("layers") or []
                    if layers_:
                        return layers_[0]
                except Exception:
                    pass
                return {}

            import time as _time
            # Ensure our synthetic timestamps are always >= the rules engine last_apply time.
            # Otherwise (tt - last_apply) can be negative and rules will not evaluate.
            last_apply = 0.0
            try:
                last_apply = float(getattr(core, "_rules_last_apply_t", 0.0) or 0.0)
            except Exception:
                last_apply = 0.0
            base = max(_time.time(), last_apply + 0.20)
            base = float(int(base)) + 0.10
            ts = [base + (i * 0.60) for i in range(10)]

            op_field_samples = []
            op_param_samples = []
            sq_samples = []
            fired_any = False
            last_fired = []
            last_errors = []
            tick_err = None

            for t in ts:
                try:
                    tick_fn(float(t))
                    fired_any = fired_any or bool(getattr(core, "_rules_last_fired_ids", []) or [])
                    last_fired = list(getattr(core, "_rules_last_fired_ids", []) or [])
                    last_errors = list(getattr(core, "_rules_last_errors", []) or [])
                except Exception as e:
                    tick_err = f"{type(e).__name__}: {e}"

                try:
                    self._audit_safe_rebuild("door_j1_tick")
                except Exception:
                    pass

                L = get_layer() or {}
                try:
                    from runtime.resolver import resolve_address
                    op_field_samples.append(resolve_address(project=getattr(core, "project", {}) or {}, address="layers[0].opacity", default=None).value)
                except Exception:
                    op_field_samples.append(None)
                params = L.get("params") or {}
                op_param_samples.append(params.get("opacity", None))
                try:
                    sig = getattr(core, "signals", None) or {}
                    sq_samples.append(sig.get("time.square1hz", None))
                except Exception:
                    sq_samples.append(None)

            # Restore
            try:
                if old_force is None:
                    delattr(core, "_force_wallclock_signals")
                else:
                    setattr(core, "_force_wallclock_signals", old_force)
            except Exception:
                pass

            r_field = sorted(set([None if v is None else round(float(v), 2) for v in op_field_samples if v is not None]))
            r_param = sorted(set([None if v is None else round(float(v), 2) for v in op_param_samples if v is not None]))

            ev = {
                "tick_error": tick_err,
                "square_samples": sq_samples[:12],
                "opacity_field_samples": op_field_samples[:12],
                "opacity_param_samples": op_param_samples[:12],
                "field_unique": r_field,
                "param_unique": r_param,
                "fired_any": fired_any,
                "last_fired": last_fired,
                "last_errors": last_errors,
            }

            # Canonical contract: Rules/runtime mutations must win on the first-class
            # layer field that preview/export consume. params["opacity"] is authored
            # effect data and should not be used as a shadow mirror for canonical
            # composition fields. Treat unchanged params as healthy rather than as a
            # failure condition.
            if 0.75 in r_field and 0.25 in r_field:
                return "[OverridePriority] PASS " + json.dumps(ev, separators=(',',':'))
            return "[OverridePriority] FAIL: did not observe expected canonical field override states " + json.dumps(ev, separators=(',',':'))

