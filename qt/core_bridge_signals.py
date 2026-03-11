from __future__ import annotations

from runtime.rules import ensure_rules, evaluate_rules


class CoreBridgeSignalsMixin:
        @property
        def preview_engine(self):
            """Live preview engine used by Qt preview widgets."""
            return self._full_preview_engine

        @property
        def project_data(self):
            """Compatibility alias for the current canonical project dict."""
            return self.project

        def get_signal_value(self, key: str, default: float = 0.0) -> float:
            """Best-effort signal lookup used by diagnostics/Rules.

            Returns default when missing/unavailable.
            """
            try:
                return float(getattr(self, "signals", {}).get(key, default))
            except Exception:
                return float(default)

        def _update_signals_from_preview(self, t: float) -> None:
            """Update the signal bus from the preview's audio + current time.

            Called from UI render paths after PreviewEngine.render_frame() so audio
            state is already stepped.
            """
            # Diagnostics harnesses can run when the preview time source is not advancing
            # (e.g. when no preview widget is actively rendering). In those cases we must
            # use wallclock time so derived signals (time.square1hz, etc.) and Rules
            # toggles actually change.
            if bool(getattr(self, "_force_wallclock_signals", False)):
                eng = None
            else:
                eng = getattr(self, "_full_preview_engine", None)
            snap = None
            try:
                if eng is not None and hasattr(eng, "time_source"):
                    snap = eng.time_source.snapshot()
            except Exception:
                snap = None

            if snap is not None:
                tt = float(getattr(snap, "t", 0.0))
                dt = float(getattr(snap, "dt", 0.0))
                # Override signal frame/tick with canonical counters
                try:
                    self._signal_frame = int(getattr(snap, "frame", 0))
                except Exception:
                    self._signal_frame = 0
                try:
                    self._signal_tick = int(getattr(snap, "tick", self._signal_frame))
                except Exception:
                    self._signal_tick = int(self._signal_frame)
                try:
                    self._signal_time_mode = str(getattr(snap, "mode", "SIM_FIXED_DT"))
                except Exception:
                    self._signal_time_mode = "SIM_FIXED_DT"
                try:
                    self._signal_time_paused = bool(getattr(snap, "paused", False))
                except Exception:
                    self._signal_time_paused = False
                try:
                    self._signal_fixed_dt = float(getattr(snap, "fixed_dt", 1.0/60.0))
                except Exception:
                    self._signal_fixed_dt = 1.0/60.0
                try:
                    self._signal_last_t = float(getattr(snap, "wall_t", tt))
                except Exception:
                    self._signal_last_t = None
            else:
                try:
                    tt = float(t)
                except Exception:
                    tt = 0.0
                last = getattr(self, '_signal_last_t', None)
                try:
                    dt = 0.0 if last is None else max(0.0, float(tt) - float(last))
                except Exception:
                    dt = 0.0
                try:
                    self._signal_last_t = tt
                except Exception:
                    self._signal_last_t = None
                try:
                    self._signal_frame = int(getattr(self, '_signal_frame', 0)) + 1
                except Exception:
                    self._signal_frame = 1
                self._signal_tick = int(self._signal_frame)
                self._signal_time_mode = "WALLCLOCK"
                self._signal_time_paused = False
                self._signal_fixed_dt = float(getattr(self, "_fixed_dt", 1.0/60.0))
            audio_state = None
            try:
                svc = getattr(self, "audio_service", None)
                if svc is not None:
                    svc.step(tt)
                    audio_state = getattr(svc, "state", None)
                else:
                    a = getattr(self, '_full_preview_audio', None)
                    if a is not None and hasattr(a, 'state'):
                        audio_state = getattr(a, 'state')
            except Exception:
                audio_state = None

            # Update signals first (time/audio + current variables runtime state)
            try:
                self._signal_bus_update_error = None
                self.signal_bus.update(
                    t=tt,
                    dt=dt,
                    frame=int(self._signal_frame),
                    time_mode=getattr(self, '_signal_time_mode', 'SIM_FIXED_DT'),
                    time_paused=bool(getattr(self, '_signal_time_paused', False)),
                    time_tick=int(getattr(self, '_signal_tick', 0)),
                    time_fixed_dt=float(getattr(self, '_signal_fixed_dt', 1.0/60.0)),
                    audio_state=audio_state,
                    variables_state=getattr(self, "_variables_state", None),
                    derived_signals={
                        # Canonical derived time signals for Rules (Phase 6.x)
                        'time.square1hz': 1.0 if (float(tt) % 1.0) < 0.5 else 0.0,
                        'time.square1hz_inv': 0.0 if (float(tt) % 1.0) < 0.5 else 1.0,
                        'time.phase1hz': float(tt) % 1.0,
                    },
                )
                        # Expose latest signals as a plain dict for diagnostics_console and legacy callers
                try:
                    self.signals = self.signal_bus.snapshot().signals
                except Exception:
                    self.signals = {}

            except Exception:
                import traceback as _tb
                try:
                    self._signal_bus_update_error = _tb.format_exc()
                except Exception:
                    self._signal_bus_update_error = 'signal_bus.update failed'

            # Phase 6.3: Evaluate rules against the signal snapshot.
            try:
                p = self.project
                # Ensure schema exists (idempotent, no churn unless missing)
                p2, ch = ensure_rules(p)
                if ch:
                    try:
                        self.project = p2
                        p = self.project
                    except Exception as e:
                        from runtime.diagnostics import GLOBAL_DIAGS
                        GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                        pass

                # Apply rules at a modest cadence to avoid UI churn.
                last_apply = float(getattr(self, "_rules_last_apply_t", 0.0) or 0.0)
                if (tt - last_apply) >= 0.05:
                    prev_state = getattr(self, "_rules_prev_state", {})
                    vstate = getattr(self, "_variables_state", {"number": {}, "toggle": {}})
                    snap = self.signal_bus.snapshot()
                    signals_now = dict(snap.signals or {})
                    # Canonical derived time signals (also mirrored into SignalBus elsewhere)
                    try:
                        _tt = float(tt)
                    except Exception:
                        _tt = 0.0
                    signals_now['time.square1hz'] = 1.0 if (_tt % 1.0) < 0.5 else 0.0
                    signals_now['time.square1hz_inv'] = 0.0 if (_tt % 1.0) < 0.5 else 1.0
                    signals_now['time.phase1hz'] = _tt % 1.0
                    res = evaluate_rules(
                        project=p,
                        signals=signals_now,
                        variables_state=vstate,
                        prev_state=prev_state,
                        allow_layer_param_mutation=True,
                    )
                    # Remember last evaluation outcomes for UI inspection
                    try:
                        self._rules_last_fired_ids = list(res.fired_rule_ids or [])
                    except Exception:
                        self._rules_last_fired_ids = []
                    try:
                        self._rules_last_errors = list(res.errors or [])
                    except Exception:
                        self._rules_last_errors = []
                    try:
                        self._rules_last_eval_t = float(tt)
                    except Exception:
                        self._rules_last_eval_t = 0.0

                    # Phase 6.5: Per-rule debug state for UI (safe/inspectable)
                    try:
                        per = getattr(self, "_rules_per_rule", None)
                        if not isinstance(per, dict):
                            per = {}
                        # Map errors by rule id (best-effort)
                        err_by: dict = {}
                        try:
                            for msg in list(res.errors or []):
                                s = str(msg)
                                # expected prefix: "rule <id>: ..."
                                if s.startswith("rule "):
                                    parts = s.split(":", 1)
                                    head = parts[0].strip()
                                    rid2 = head.replace("rule", "").strip()
                                    if rid2:
                                        err_by[rid2] = s
                        except Exception:
                            err_by = {}
                        # Build state snapshot for each rule in project
                        try:
                            rules0 = (p.get("rules") or [])
                            rules_list2 = list(rules0) if isinstance(rules0, list) else []
                        except Exception:
                            rules_list2 = []
                        for rr0 in rules_list2:
                            rr = rr0 if isinstance(rr0, dict) else {}
                            rid2 = str(rr.get("id", "") or "")
                            if not rid2:
                                continue
                            d = per.get(rid2) if isinstance(per.get(rid2), dict) else {}
                            d = dict(d)
                            trig2 = str(rr.get("trigger", "tick") or "tick")
                            # Current trigger "state" as tracked in prev_state
                            st = None
                            try:
                                if trig2 == "rising":
                                    st = bool(prev_state.get(f"rise:{rid2}", False))
                                elif trig2 == "threshold":
                                    st = bool(prev_state.get(f"thr:{rid2}", False))
                                elif trig2 == "tick":
                                    st = True
                            except Exception:
                                st = None
                            d["trigger"] = trig2
                            d["state"] = st
                            try:
                                d["cond_ok"] = bool(prev_state.get(f"cond:{rid2}", True))
                            except Exception:
                                d["cond_ok"] = True
                            d["enabled"] = bool(rr.get("enabled", True))
                            d["name"] = str(rr.get("name", "") or "")
                            d["last_eval_t"] = float(tt)
                            if rid2 in list(res.fired_rule_ids or []):
                                d["last_fire_t"] = float(tt)
                            if rid2 in err_by:
                                d["last_error"] = str(err_by[rid2])
                            else:
                                # Clear previous error once it stops happening
                                d.pop("last_error", None)
                            per[rid2] = d
                        self._rules_per_rule = per
                    except Exception as e:
                        from runtime.diagnostics import GLOBAL_DIAGS
                        GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                        pass
                    # Update runtime variables state
                    try:
                        self._variables_state = res.variables_state
                        self._variables_runtime_dirty = True
                        try:
                            self._variables_rev = int(getattr(self, '_variables_rev', 0)) + 1
                        except Exception:
                            self._variables_rev = 1
                    except Exception as e:
                        from runtime.diagnostics import GLOBAL_DIAGS
                        GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                        pass

                    # Apply layer param mutations into project (rare, only when fired)
                    try:
                        muts = res.project_mutations.get("layer_param") if isinstance(res.project_mutations, dict) else None
                    except Exception:
                        muts = None
                    if muts:
                        try:
                            applied = False
                            project_after_pm = None
                            if hasattr(self, 'pm') and self.pm is not None and hasattr(self.pm, 'apply_rule_layer_mutations'):
                                try:
                                    active_layer = int(self.get_selected_layer())
                                except Exception:
                                    active_layer = -1
                                try:
                                    applied = bool(self.pm.apply_rule_layer_mutations(muts, active_layer=active_layer))
                                except Exception as e:
                                    from runtime.diagnostics import GLOBAL_DIAGS
                                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                                    applied = False
                                if hasattr(self.pm, 'get'):
                                    try:
                                        project_after_pm = self.pm.get()
                                    except Exception:
                                        project_after_pm = None

                            # Canonical live-project sync: regardless of whether PM reported success,
                            # re-apply canonical mutations onto the CURRENT CoreBridge.project dict and
                            # then mirror that exact dict back into PM. This closes the remaining split
                            # where Rules fire against a stale PM snapshot, PM returns/applies truthily,
                            # but CoreBridge.project / preview still render the pre-mutation layer fields.
                            try:
                                from runtime.resolver import set_address
                                from runtime.canonical_addr import canonicalize_layer_param_name
                                pseed = project_after_pm if isinstance(project_after_pm, dict) else (getattr(self, 'project', {}) if isinstance(getattr(self, 'project', {}), dict) else {})
                                pnow = dict(pseed or {})
                                changed = False
                                for item in list(muts or []):
                                    try:
                                        li, param, val = item
                                        li = int(li)
                                        tgt = canonicalize_layer_param_name(str(param or ''))
                                    except Exception:
                                        continue
                                    addr = None
                                    if tgt is not None:
                                        if tgt.scope == 'layer_field':
                                            addr = f"layers[{li}].{tgt.key}"
                                        elif tgt.scope == 'project_postfx':
                                            addr = f"project.postfx.{tgt.key}"
                                        elif tgt.scope == 'operator_param':
                                            addr = f"layers[{li}]._op_overrides.{tgt.key}"
                                    if not addr:
                                        continue
                                    try:
                                        pnew, did = set_address(project=pnow, address=addr, value=val)
                                    except Exception:
                                        continue
                                    if did:
                                        pnow = pnew
                                        changed = True
                                # Even when changed == False, pnow may already contain the wanted values
                                # from PM. Make CoreBridge.project follow that single canonical dict.
                                if isinstance(pnow, dict) and pnow:
                                    self.project = pnow
                                    project_after_pm = pnow
                                    applied = bool(applied or changed)
                                    try:
                                        if hasattr(self, 'pm') and self.pm is not None:
                                            self.pm.project = dict(pnow)
                                            try:
                                                self.pm.dirty = True
                                            except Exception:
                                                pass
                                            try:
                                                self.pm._notify()
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            except Exception as e:
                                from runtime.diagnostics import GLOBAL_DIAGS
                                GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})

                            if applied:
                                try:
                                    self._preview_dirty = True
                                except Exception as e:
                                    from runtime.diagnostics import GLOBAL_DIAGS
                                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                                    pass
                                try:
                                    if hasattr(self, 'rebuild_preview'):
                                        self.rebuild_preview('rules_layer_param')
                                except Exception as e:
                                    from runtime.diagnostics import GLOBAL_DIAGS
                                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                                    pass
                        except Exception as e:
                            from runtime.diagnostics import GLOBAL_DIAGS
                            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                            pass

                    try:
                        self._rules_last_apply_t = float(tt)
                    except Exception:
                        self._rules_last_apply_t = last_apply
            except Exception:
                import traceback as _tb
                try:
                    self._rules_exception = _tb.format_exc()
                except Exception:
                    self._rules_exception = 'rules failed'
                try:
                    tail = None
                    try:
                        tail = str(self._rules_exception).splitlines()[-1]
                    except Exception:
                        tail = str(self._rules_exception)
                    self._rules_last_errors = [f"EXCEPTION: {tail}"]
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
