from __future__ import annotations

import json
import time

from qt.qt_compat import QtWidgets  # type: ignore

from qt.diagnostics_console_doors_utils import DiagnosticsConsoleDoorsUtilityMixin
from qt.diagnostics_console_doors_probes import DiagnosticsConsoleDoorsProbeMixin

class DiagnosticsConsoleDoorsExecutionMixin:
        def _run_selected_target(self) -> None:
            """Backward-compatible entry point; suites now run through the single diagnostics runner."""
            if getattr(self, '_audit_running', False):
                self._log('[Audit] Busy: diagnostics already running')
                return
            try:
                code = self.cmb_run_target.currentData()
            except Exception:
                code = None

            if not code:
                self._log("[Audit] Select a door from the dropdown first.")
                return

            # Read repeat controls (best-effort; defaults are safe).
            repeats = 1
            clean_each = True
            try:
                repeats = int(getattr(self, "spn_repeat", None).value())
            except Exception:
                repeats = 1
            try:
                clean_each = bool(getattr(self, "chk_clean_each", None).isChecked())
            except Exception:
                clean_each = True

            return self._run_door_repeated(code, repeats=repeats, clean_each=clean_each)

        def _run_door_f1_only(self) -> None:
            # Backwards compat: older builds had a dedicated button.
            return self._run_single_door("F1")

        def _run_door_repeated(self, code: str, *, repeats: int = 20, clean_each: bool = True) -> None:
            """Run a door multiple times and summarize flakiness."""
            repeats = max(1, int(repeats or 1))
            if getattr(self, '_audit_running', False):
                self._log('[Audit] Busy: diagnostics already running')
                return

            self._set_audit_busy(True, f'Running DOOR {code} ×{repeats}…')
            try:
                if hasattr(self, "prg_runs") and self.prg_runs is not None:
                    self.prg_runs.setRange(0, repeats)
                    self.prg_runs.setValue(0)
                    self.prg_runs.setFormat(f"Running {code}… 0/{repeats}")
            except Exception:
                pass
            def _run_body():
                started = time.time()
                run_id = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())

                report = {
                    "title": f"DOOR {code} REPEAT",
                    "id": f"DOOR_{code}_REPEAT{repeats}_{run_id}",
                    "started_utc": run_id,
                    "duration_s": None,
                    "overall": "UNKNOWN",
                    "first_fail": None,
                    "steps": [],
                    "repeat": {"door": code, "repeats": repeats, "clean_each": bool(clean_each)},
                }

                def add_step(step_id: str, status: str, summary: str, details: dict | None = None):
                    report["steps"].append({
                        "id": step_id,
                        "status": status,
                        "summary": summary,
                        "details": details or {},
                    })

                # UI reset
                self._log("")
                self._log(f"=== RUN DOOR {code} ×{repeats} (clean_each={clean_each}) ===")
                if code in ("D1", "F1"):
                    self._log(f"[Audit] Note: {code} can take a few seconds per run — this is expected.")
                try:
                    self.lbl_audit_summary.setText(f"Running DOOR {code} ×{repeats}…")
                    self.txt_audit_details.setPlainText("")
                except Exception:
                    pass

                passes = 0
                fails = 0
                first_fail_details = None

                for i in range(1, repeats + 1):
                    # Progress tick (keeps UI visibly alive on slower doors).
                    try:
                        if hasattr(self, "prg_runs") and self.prg_runs is not None:
                            self.prg_runs.setValue(i - 1)
                            self.prg_runs.setFormat(f"Running {code}… {i-1}/{repeats}")
                        QtWidgets.QApplication.processEvents()
                    except Exception:
                        pass

                    # Fingerprint authored state before the run (detect carry-forward mutations).
                    fp_before, state_before = self._project_fingerprint()
                    def _once():
                        return self._run_door_once(code)

                    try:
                        if clean_each:
                            ok, summ, details = self._with_clean_diagnostics_sandbox(_once)
                        else:
                            ok, summ, details = _once()
                    except Exception as e:
                        ok, summ, details = False, f"ERROR: {e!r}", {"exception": repr(e)}


                    # Fingerprint after the run; detect *authored project* mutations.
                    fp_after, state_after = self._project_fingerprint()
                    try:
                        d = self._shallow_dict_diff(state_before.get("project") or {}, state_after.get("project") or {})
                    except Exception:
                        d = {"added": [], "removed": [], "changed": []}

                    # Always attach fingerprints for post-mortem debugging.
                    try:
                        if isinstance(details, dict):
                            details.setdefault("_state_fingerprint", {})
                            details["_state_fingerprint"].update({
                                "before": fp_before,
                                "after": fp_after,
                                "diff_top": d,
                            })
                        else:
                            details = {"_state_fingerprint": {"before": fp_before, "after": fp_after, "diff_top": d}}
                    except Exception:
                        pass

                    # Warn only if the authored project actually changed (top-level diff non-empty).
                    if fp_after != fp_before and (d.get("added") or d.get("removed") or d.get("changed")):
                        self._log(f"[{code}.run{i:02d}] WARN — door mutated authored project state (unexpected)")
                    step_id = f"{code}.run{i:02d}"
                    if ok:
                        passes += 1
                        add_step(step_id, "PASS", summ, details)
                        self._log(f"[{step_id}] PASS — {summ}")
                    else:
                        fails += 1
                        add_step(step_id, "FAIL", summ, details)
                        self._log(f"[{step_id}] FAIL — {summ}")
                        if report["first_fail"] is None:
                            report["first_fail"] = {"id": step_id, "summary": summ}
                            first_fail_details = details

                    try:
                        if hasattr(self, "prg_runs") and self.prg_runs is not None:
                            self.prg_runs.setValue(i)
                            self.prg_runs.setFormat(f"Running {code}… {i}/{repeats}")
                        QtWidgets.QApplication.processEvents()
                    except Exception:
                        pass

                report["overall"] = "PASS" if fails == 0 else "FAIL"

                # Human summary
                try:
                    msg = f"DOOR {code} ×{repeats}: PASS={passes} FAIL={fails} (clean_each={clean_each})"
                    self.lbl_audit_summary.setText(msg)
                    self.txt_audit_details.setPlainText(json.dumps({
                        "door": code,
                        "repeats": repeats,
                        "clean_each": bool(clean_each),
                        "passes": passes,
                        "fails": fails,
                        "first_fail": report.get("first_fail"),
                        "first_fail_details": first_fail_details,
                    }, indent=2, sort_keys=False))
                except Exception:
                    pass

                return self._finalize_audit(report, started)

            try:
                return _run_body()
            finally:
                try:
                    if hasattr(self, "prg_runs") and self.prg_runs is not None:
                        self.prg_runs.setFormat("Done")
                except Exception:
                    pass
                self._set_audit_busy(False)

        def _run_door_once(self, code: str):
            """Execute the door probe once and return (ok, summary, details)."""
            if code == "A1":
                out = self._probe_layer_wiring()
                ok = ("ERROR" not in out)
                return ok, ("Layer wiring OK" if ok else "Layer wiring ERROR"), {"out": out}
            if code == "A2":
                out = self._probe_surface_mapping()
                ok = ("ERROR" not in out)
                return ok, ("Surface/mapping OK" if ok else "Surface/mapping ERROR"), {"out": out}
            if code == "B1":
                out = self._probe_mapping_parity("quick")
                ok = ("ERROR" not in out and "MISMATCH" not in out and "FAIL" not in out)
                return ok, ("Mapping parity (quick) OK" if ok else "Mapping parity mismatch/error"), {"out": out}
            if code == "C1":
                ok, details = self._run_composition_door_suite_audit()
                summ = details.get("summary", "Composition atomic suite") if isinstance(details, dict) else "Composition atomic suite"
                return bool(ok), summ, (details if isinstance(details, dict) else {"details": details})
            if code == "D1":
                ok, details = self._run_coupled_composition_suite_audit()
                summ = details.get("summary", "Coupled composition suite") if isinstance(details, dict) else "Coupled composition suite"
                return bool(ok), summ, (details if isinstance(details, dict) else {"details": details})
            if code == "E1":
                out = self._probe_full_health()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Full health OK" if ok else "Full health FAIL"), {"out": out}
            if code == "F1":
                out = self._probe_operator_overrides()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Operator overrides OK" if ok else "Operator overrides FAIL"), {"out": out}
            if code == "G1":
                out = self._probe_time_signals()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Time signals OK" if ok else "Time signals FAIL"), {"out": out}
            if code == "H1":
                out = self._probe_audio_signals()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Audio signals OK" if ok else "Audio signals FAIL"), {"out": out}
            if code == "I1":
                out = self._probe_canonical_resolver()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Canonical resolver OK" if ok else "Canonical resolver FAIL"), {"out": out}
            if code == "J1":
                out = self._probe_override_priority()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Override priority OK" if ok else "Override priority FAIL"), {"out": out}
            if code == "K1":
                out = self._probe_persistence_policy()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Persistence policy OK" if ok else "Persistence policy FAIL"), {"out": out}
            if code == "L1":
                out = self._probe_export_canonical_params_quick()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Export canonical params OK" if ok else "Export canonical params FAIL"), {"out": out}
            if code == "M1":
                out = self._probe_preview_export_semantic_parity()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Preview↔Export semantic parity OK" if ok else "Preview↔Export semantic parity FAIL"), {"out": out}
            if code == "N1":
                out = self._probe_audit_lock()
                ok = ("PASS" in out and "FAIL" not in out and "ERROR" not in out)
                return ok, ("Audit lock OK" if ok else "Audit lock FAIL"), {"out": out}

            return False, "Unknown door code", {"code": code}

        def _run_single_door(self, code: str) -> None:
            if getattr(self, '_audit_running', False):
                self._log('[Audit] Busy: diagnostics already running')
                return
            self._set_audit_busy(True, f'Running DOOR {code}…')
            def _run_body():
                core = getattr(self, "app_core", None)
                if core is None:
                    self._log("[Audit] No app_core")
                    return

                started = time.time()
                run_id = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())

                report = {
                    "title": f"DOOR {code}",
                    "id": f"DOOR_{code}_{run_id}",
                    "started_utc": run_id,
                    "duration_s": None,
                    "overall": "UNKNOWN",
                    "first_fail": None,
                    "steps": [],
                }

                def add_step(step_id: str, status: str, summary: str, details: dict | None = None):
                    report["steps"].append({
                        "id": step_id,
                        "status": status,
                        "summary": summary,
                        "details": details or {},
                    })

                # UI reset
                self._log("")
                self._log(f"=== RUN DOOR {code} ===")
                try:
                    self.lbl_audit_summary.setText(f"Running DOOR {code}…")
                    self.txt_audit_details.setPlainText("")
                except Exception:
                    pass

                # Dispatch
                if code == "A1":
                    out = self._probe_layer_wiring()
                    if "ERROR" in out:
                        add_step("A1.LAYER_WIRING", "FAIL", "Layer wiring inspector errored", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "A1.LAYER_WIRING", "summary": "Layer wiring inspector errored"}
                    else:
                        add_step("A1.LAYER_WIRING", "PASS", "Layer wiring inspector ran", {"out": out})
                        report["overall"] = "PASS"

                elif code == "A2":
                    out = self._probe_surface_mapping()
                    if "ERROR" in out:
                        add_step("A2.SURFACE_MAPPING", "FAIL", "Surface/mapping inspector errored", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "A2.SURFACE_MAPPING", "summary": "Surface/mapping inspector errored"}
                    else:
                        add_step("A2.SURFACE_MAPPING", "PASS", "Surface/mapping inspector ran", {"out": out})
                        report["overall"] = "PASS"

                elif code == "B1":
                    out = self._probe_mapping_parity("quick")
                    if "ERROR" in out or "MISMATCH" in out or "FAIL" in out:
                        add_step("B1.MAPPING_PARITY", "FAIL", "Mapping parity probe reports mismatch/error", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "B1.MAPPING_PARITY", "summary": "Mapping parity probe reports mismatch/error"}
                    else:
                        add_step("B1.MAPPING_PARITY", "PASS", "Mapping parity (quick) OK", {"out": out})
                        report["overall"] = "PASS"

                elif code == "C1":
                    ok, details = self._run_composition_door_suite_audit()
                    if not ok:
                        add_step("C1.COMPOSITION_ATOMIC", "FAIL", details.get("summary", "Composition atomic suite failed"), details)
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "C1.COMPOSITION_ATOMIC", "summary": details.get("summary", "Composition atomic suite failed")}
                    else:
                        add_step("C1.COMPOSITION_ATOMIC", "PASS", "Composition atomic doors proved", details)
                        report["overall"] = "PASS"

                elif code == "D1":
                    ok, details = self._run_coupled_composition_suite_audit()
                    if not ok:
                        add_step("D1.COMPOSITION_COUPLED", "FAIL", details.get("summary", "Coupled composition suite failed"), details)
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "D1.COMPOSITION_COUPLED", "summary": details.get("summary", "Coupled composition suite failed")}
                    else:
                        add_step("D1.COMPOSITION_COUPLED", "PASS", "Coupled composition interactions proved", details)
                        report["overall"] = "PASS"

                elif code == "E1":
                    out = self._probe_full_health()
                    if "ERROR" in out or "FAIL" in out:
                        add_step("E1.FULL_HEALTH", "FAIL", "Full health check reports issues", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "E1.FULL_HEALTH", "summary": "Full health check reports issues"}
                    else:
                        add_step("E1.FULL_HEALTH", "PASS", "Full health check OK", {"out": out})
                        report["overall"] = "PASS"

                elif code == "F1":
                    out = self._probe_operator_overrides()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("F1.OPERATOR_OVERRIDES", "PASS", "Operator override probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("F1.OPERATOR_OVERRIDES", "FAIL", "Operator override probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "F1.OPERATOR_OVERRIDES", "summary": "Operator override probe failed"}

                elif code == "G1":
                    out = self._probe_time_signals()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("G1.TIME_SIGNALS", "PASS", "Time signal bus probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("G1.TIME_SIGNALS", "FAIL", "Time signal bus probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "G1.TIME_SIGNALS", "summary": "Time signal bus probe failed"}
                elif code == "H1":
                    out = self._probe_audio_signals()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("H1.AUDIO_SIGNALS", "PASS", "Audio signal bus probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("H1.AUDIO_SIGNALS", "FAIL", "Audio signal bus probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "H1.AUDIO_SIGNALS", "summary": "Audio signal bus probe failed"}

                elif code == "I1":
                    out = self._probe_canonical_resolver()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("I1.CANONICAL_RESOLVER", "PASS", "Canonical address resolver probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("I1.CANONICAL_RESOLVER", "FAIL", "Canonical address resolver probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "I1.CANONICAL_RESOLVER", "summary": "Canonical address resolver probe failed"}

                elif code == "J1":
                    out = self._probe_override_priority()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("J1.OVERRIDE_PRIORITY", "PASS", "Override priority probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("J1.OVERRIDE_PRIORITY", "FAIL", "Override priority probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "J1.OVERRIDE_PRIORITY", "summary": "Override priority probe failed"}

                elif code == "K1":
                    out = self._probe_persistence_policy()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("K1.PERSISTENCE_POLICY", "PASS", "Persistence policy probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("K1.PERSISTENCE_POLICY", "FAIL", "Persistence policy probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "K1.PERSISTENCE_POLICY", "summary": "Persistence policy probe failed"}
                elif code == "L1":
                    out = self._probe_export_canonical_params_quick()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("L1.EXPORT_CANONICAL_PARAMS", "PASS", "Export canonical params probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("L1.EXPORT_CANONICAL_PARAMS", "FAIL", "Export canonical params probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "L1.EXPORT_CANONICAL_PARAMS", "summary": "Export canonical params probe failed"}
                elif code == "N1":
                    out = self._probe_audit_lock()
                elif code == "N1":
                    out = self._probe_audit_lock()
                elif code == "M1":
                    out = self._probe_preview_export_semantic_parity()
                    if "PASS" in out and "FAIL" not in out and "ERROR" not in out:
                        add_step("M1.PREVIEW_EXPORT_SEMANTIC_PARITY", "PASS", "Preview↔Export semantic parity probe OK", {"out": out})
                        report["overall"] = "PASS"
                    else:
                        add_step("M1.PREVIEW_EXPORT_SEMANTIC_PARITY", "FAIL", "Preview↔Export semantic parity probe failed", {"out": out})
                        report["overall"] = "FAIL"
                        report["first_fail"] = {"id": "M1.PREVIEW_EXPORT_SEMANTIC_PARITY", "summary": "Preview↔Export semantic parity probe failed"}





                else:
                    add_step(f"DOOR_{code}", "FAIL", "Unknown door code", {"code": code})
                    report["overall"] = "FAIL"
                    report["first_fail"] = {"id": f"DOOR_{code}", "summary": "Unknown door code"}

                return self._finalize_audit(report, started)

            try:
                return self._with_clean_diagnostics_sandbox(_run_body)
            finally:
                self._set_audit_busy(False)
