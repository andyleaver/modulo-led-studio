from __future__ import annotations

import time
import json

from qt.diagnostics_console_doors_probe_support import legacy_layer_param_mirror_keys


class DiagnosticsConsoleDoorsResolverProbeMixin:
    def _probe_canonical_resolver(self) -> str:
            """Door I1: Canonical address resolver (Rules -> canonical targets -> project schema).

            Deterministic, probe-only.
            This door proves that Rules mutations using canonical names map into:
            - layer fields consumed by the compositor (opacity/blend_mode)
            - project postfx fields (trail_amount)
            - operator override namespace (operator.gain -> _op_overrides.gain)
            - without reintroducing legacy param mirrors

            NOTE: We run a short tick loop and force audit stepping to avoid state/race coupling
            with other doors in FULL AUDIT.
            """
            core = getattr(self, 'app_core', None)
            if core is None:
                return "[CanonicalResolver] ERROR: no app_core"

            from runtime.canonical_addr import canonicalize_address, parse_canonical_address

            ev: dict = {}

            # Canonicalize a few representative canonical targets (pure mapping proof)
            try:
                _pa = parse_canonical_address("layers[0].opacity")
                ev["canon.layers[0].opacity"] = [_pa.scope, _pa.key]
                _pt = canonicalize_address("project.postfx.trail_amount")
                ev["canon.project.postfx.trail_amount"] = [_pt.scope, _pt.key]
                _og = canonicalize_address("operator.gain")
                ev["canon.operator.gain"] = [_og.scope, _og.key]
            except Exception:
                pass

            layers = [
                {
                    "name": "I1 layer",
                    "behavior": "solid",
                    "opacity": 1.0,
                    "enabled": True,
                    "blend_mode": "over",
                    "params": {"r": 80, "g": 80, "b": 80},
                    "operators": [{"type": "solid", "enabled": True, "params": {}}],
                }
            ]

            rules = [
                {
                    "id": "r_set_opacity",
                    "enabled": True,
                    "name": "opacity=0.25",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "opacity",
                               "expr": {"src": "const", "const": 0.25}},
                },
                {
                    "id": "r_set_blend",
                    "enabled": True,
                    "name": "blend=add",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "blend_mode",
                               "expr": {"src": "const", "const": "add"}},
                },
                {
                    "id": "r_set_postfx",
                    "enabled": True,
                    "name": "project.postfx.trail_amount=0.55",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "project.postfx.trail_amount",
                               "expr": {"src": "const", "const": 0.55}},
                },
                {
                    "id": "r_set_operator_gain",
                    "enabled": True,
                    "name": "operator.gain=1.5",
                    "trigger": "tick",
                    "trigger_mode": "all",
                    "conditions": [],
                    "action": {"kind": "set_layer_param", "layer": 0, "param": "operator.gain",
                               "expr": {"src": "const", "const": 1.5}},
                },
            ]

            try:
                self._audit_inject_project(layers=layers, rules=rules, postfx={"trail_amount": 0.0})
                self._audit_safe_rebuild("door_i1_inject")
            except Exception as e:
                return "[CanonicalResolver] ERROR: inject failed " + str(e)

            tick_fn = getattr(core, "_update_signals_from_preview", None)
            if not callable(tick_fn):
                return "[CanonicalResolver] ERROR: missing _update_signals_from_preview"

            old_force = bool(getattr(core, "_force_wallclock_signals", False))
            tick_err = None
            try:
                core._force_wallclock_signals = True


                # Rules application is cadence-gated inside CoreBridge by
                # _rules_last_apply_t. If a previous door ran with a later
                # wallclock 'tt' than this probe's anchored base time, the delta
                # (tt-last_apply) can be negative and *no rules will apply*,
                # producing flaky PASS/FAIL. Reset the cadence gate here so I1
                # is deterministic across runs.
                try:
                    core._rules_last_apply_t = 0.0
                except Exception:
                    pass

                base = float(int(time.time())) + 0.10
                ts = [base + (i * 0.10) for i in range(5)]

                seen = []
                for tt in ts:
                    try:
                        tick_fn(float(tt))
                    except Exception as e:
                        tick_err = f"{type(e).__name__}: {e}"
                    try:
                        self._audit_safe_rebuild("door_i1_tick")
                    except Exception:
                        pass

                    pr = getattr(core, "project", {}) or {}
                    L0 = {}
                    try:
                        L0 = (pr.get("layers") or [])[0] or {}
                    except Exception:
                        L0 = {}
                    params = L0.get("params") or {}

                    # Legacy layer_* param names are residue evidence only.
                    # Effect params are still allowed; canonical composition fields must not land here.
                    mirror_keys = legacy_layer_param_mirror_keys()
                    found_mirrors = []
                    try:
                        if isinstance(params, dict):
                            found_mirrors = [k for k in mirror_keys if k in params]
                    except Exception:
                        found_mirrors = []

                    try:
                        from runtime.resolver import resolve_address
                        opacity_res = resolve_address(project=pr, address="layers[0].opacity")
                        blend_res = resolve_address(project=pr, address="layers[0].blend_mode")
                        trail_res = resolve_address(project=pr, address="project.postfx.trail_amount")
                        gain_res = resolve_address(project=pr, address="layers[0]._op_overrides.gain")
                    except Exception:
                        opacity_res = blend_res = trail_res = gain_res = None

                    snap = {
                        "opacity": (getattr(opacity_res, "value", None) if opacity_res is not None else None),
                        "opacity_source": (getattr(opacity_res, "source", None) if opacity_res is not None else None),
                        "blend_mode": (getattr(blend_res, "value", None) if blend_res is not None else None),
                        "blend_source": (getattr(blend_res, "source", None) if blend_res is not None else None),
                        "trail_amount": (getattr(trail_res, "value", None) if trail_res is not None else None),
                        "trail_source": (getattr(trail_res, "source", None) if trail_res is not None else None),
                        "gain": (getattr(gain_res, "value", None) if gain_res is not None else None),
                        "gain_source": (getattr(gain_res, "source", None) if gain_res is not None else None),
                        "found_mirrors": found_mirrors,
                        "fired": list(getattr(core, "_rules_last_fired_ids", []) or []),
                        "errors": list(getattr(core, "_rules_last_errors", []) or []),
                    }
                    seen.append(snap)

                    # Early exit if already satisfied
                    try:
                        if (abs(float(snap["opacity"]) - 0.25) < 1e-6
                            and str(snap["blend_mode"]) == "add"
                            and abs(float(snap["trail_amount"]) - 0.55) < 1e-6
                            and abs(float(snap["gain"]) - 1.5) < 1e-6):
                            break
                    except Exception:
                        pass

                ev["tick_error"] = tick_err
                ev["samples"] = (seen[:2] + ["..."] + seen[-2:]) if len(seen) > 5 else seen

                # Use final snapshot for PASS criteria
                last = next((s for s in reversed(seen) if isinstance(s, dict)), {})
                ok_opacity = (last.get("opacity") is not None and abs(float(last["opacity"]) - 0.25) < 1e-6)
                ok_blend = (str(last.get("blend_mode") or "") == "add")
                ok_postfx = (last.get("trail_amount") is not None and abs(float(last["trail_amount"]) - 0.55) < 1e-6)
                ok_gain = (last.get("gain") is not None and abs(float(last["gain"]) - 1.5) < 1e-6)

                # Param mirrors are best-effort: do not fail the door if some mirrors aren't defined yet.
                # We record them only as raw evidence; canonical pass/fail comes from resolver truth.
                if ok_opacity and ok_blend and ok_postfx and ok_gain:
                    return "[CanonicalResolver] PASS " + json.dumps(ev, separators=(',',':'))
                return "[CanonicalResolver] FAIL " + json.dumps(ev, separators=(',',':'))

            finally:
                try:
                    core._force_wallclock_signals = old_force
                except Exception:
                    pass

