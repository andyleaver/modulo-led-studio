from __future__ import annotations

import time

from qt.diagnostics_console_full_audit_probes import DiagnosticsConsoleFullAuditProbeMixin
from qt.diagnostics_console_full_audit_finalize import DiagnosticsConsoleFullAuditFinalizeMixin


class DiagnosticsConsoleFullAuditMixin(
    DiagnosticsConsoleFullAuditProbeMixin,
    DiagnosticsConsoleFullAuditFinalizeMixin,
):
    def _run_full_audit(self) -> None:
        if getattr(self, '_audit_running', False):
            self._log('[Audit] Busy: diagnostics already running')
            return
        self._set_audit_busy(True, 'Running FULL AUDIT…')
        def _run_body():
            """RUN FULL AUDIT (All Doors Open).

            Design:
            - Single entry point (one button) to prove doors are open.
            - Fail-fast: stop on first failing step and point to the exact door.
            - Persist a machine-readable report under ../artifacts/diagnostics_runs/...
            """
            core = getattr(self, "app_core", None)
            if core is None:
                self._log("[Audit] No app_core")
                return

            started = time.time()
            run_id = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())
            report = {
                "id": f"FULL_AUDIT_{run_id}",
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

            def mark_fail(step_id: str, summary: str, details: dict | None = None):
                add_step(step_id, "FAIL", summary, details)
                report["overall"] = "FAIL"
                report["first_fail"] = {"id": step_id, "summary": summary}
                return False

            def mark_pass(step_id: str, summary: str, details: dict | None = None):
                add_step(step_id, "PASS", summary, details)
                return True

            def mark_warn(step_id: str, summary: str, details: dict | None = None):
                add_step(step_id, "WARN", summary, details)
                return True

            def fail_fast_check(ok: bool) -> bool:
                return ok

            # UI reset
            self._log("")
            self._log("=== RUN FULL AUDIT (All Doors Open) ===")
            self._log("Fail-fast: stops on first failing door and prints evidence.")
            try:
                self.lbl_audit_summary.setText("Running FULL AUDIT…")
                self.txt_audit_details.setPlainText("")
            except Exception:
                pass

            # ---- Phase A: Static sanity (fast) ----
            #  A1: Project schema / wiring inspectors (does not mutate)
            out = self._probe_layer_wiring()
            if "ERROR" in out:
                if not fail_fast_check(mark_fail("A1.LAYER_WIRING", "Layer wiring inspector errored", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("A1.LAYER_WIRING", "Layer wiring inspector ran", {"out": out})

            out = self._probe_surface_mapping()
            if "ERROR" in out:
                if not fail_fast_check(mark_fail("A2.SURFACE_MAPPING", "Surface/mapping inspector errored", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("A2.SURFACE_MAPPING", "Surface/mapping inspector ran", {"out": out})

            # ---- Phase B: Mapping parity ----
            out = self._probe_mapping_parity("quick")
            if "ERROR" in out or "MISMATCH" in out or "FAIL" in out:
                if not fail_fast_check(mark_fail("B1.MAPPING_PARITY", "Mapping parity probe reports mismatch/error", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("B1.MAPPING_PARITY", "Mapping parity (quick) OK", {"out": out})

            # Atomic composition doors
            ok, details = self._run_composition_door_suite_audit()
            if not ok:
                if not fail_fast_check(mark_fail("C1.COMPOSITION_ATOMIC", details.get("summary","Composition atomic suite failed"), details)):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("C1.COMPOSITION_ATOMIC", "Composition atomic doors proved", details)

            # ---- Phase D: Coupled composition + temporal coherency ----
            ok, details = self._run_coupled_composition_suite_audit()
            if not ok:
                if not fail_fast_check(mark_fail("D1.COMPOSITION_COUPLED", details.get("summary","Coupled composition suite failed"), details)):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("D1.COMPOSITION_COUPLED", "Coupled composition interactions proved", details)

            # ---- Phase F: Operator overrides (preview) ----
            out = self._probe_operator_overrides()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("F1.OPERATOR_OVERRIDES", "Operator override probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("F1.OPERATOR_OVERRIDES", "Operator override probe OK", {"out": out})

            # ---- Phase G: Time signals (canonical) ----
            out = self._probe_time_signals()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("G1.TIME_SIGNALS", "Time signal bus probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("G1.TIME_SIGNALS", "Time signal bus probe OK", {"out": out})


            # ---- Phase H: Audio signals (canonical, SIM) ----
            out = self._probe_audio_signals()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("H1.AUDIO_SIGNALS", "Audio signal bus probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("H1.AUDIO_SIGNALS", "Audio signal bus probe OK", {"out": out})

            # ---- Phase I: Canonical resolver (rules->project mutations) ----
            out = self._probe_canonical_resolver()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("I1.CANONICAL_RESOLVER", "Canonical address resolver probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("I1.CANONICAL_RESOLVER", "Canonical address resolver probe OK", {"out": out})

            # ---- Phase J: Override priority (rules vs authored) ----
            out = self._probe_override_priority()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("J1.OVERRIDE_PRIORITY", "Override priority probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("J1.OVERRIDE_PRIORITY", "Override priority probe OK", {"out": out})

            # ---- Phase K: Persistence policy (round-trip) ----
            out = self._probe_persistence_policy()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("K1.PERSISTENCE_POLICY", "Persistence policy probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("K1.PERSISTENCE_POLICY", "Persistence policy probe OK", {"out": out})

            # ---- Phase L: Export canonical params (quick) ----
            out = self._probe_export_canonical_params_quick()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("L1.EXPORT_CANONICAL_PARAMS", "Export canonical params probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("L1.EXPORT_CANONICAL_PARAMS", "Export canonical params probe OK", {"out": out})


            # ---- Phase M: Preview↔Export semantic parity (controlled) ----
            out = self._probe_preview_export_semantic_parity()
            if "PASS" not in out or "FAIL" in out or "ERROR" in out:
                if not fail_fast_check(mark_fail("M1.PREVIEW_EXPORT_SEMANTIC_PARITY", "Preview↔Export semantic parity probe failed", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("M1.PREVIEW_EXPORT_SEMANTIC_PARITY", "Preview↔Export semantic parity probe OK", {"out": out})

# ---- Phase E: Full health check (slow-ish but important) ----
            out = self._probe_full_health()
            if "ERROR" in out or "FAIL" in out:
                if not fail_fast_check(mark_fail("E1.FULL_HEALTH", "Full health check reports issues", {"out": out})):
                    return self._finalize_audit(report, started)
            else:
                mark_pass("E1.FULL_HEALTH", "Full health check OK", {"out": out})

            report["overall"] = "PASS"
            return self._finalize_audit(report, started)

        try:
            return self._with_clean_diagnostics_sandbox(_run_body)
        finally:
            self._set_audit_busy(False)


