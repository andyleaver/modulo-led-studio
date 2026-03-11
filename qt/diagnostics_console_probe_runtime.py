from __future__ import annotations

import time
import json
import hashlib
from typing import Callable

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from app.project_model import get_surface_snapshot


def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    """Legacy params keys that should never mirror canonical layer fields.

    These keys remain diagnostics-only residue checks. Canonical composition
    fields live on the layer object itself, not under layer.params.
    """
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )

class DiagnosticsConsoleProbeRuntimeMixin:
    def _toggle_heartbeat(self) -> None:
        self._heartbeat_enabled = not self._heartbeat_enabled
        if self._heartbeat_enabled:
            self._hb_ticks = 0
            self._hb_timer.start()
            self.btn_hb.setText("Stop Heartbeat")
            self._log("[Heartbeat] started (20Hz).")
        else:
            self._hb_timer.stop()
            self.btn_hb.setText("Start Heartbeat")
            self._log("[Heartbeat] stopped.")

    def _heartbeat_tick(self) -> None:
        if not self._heartbeat_enabled:
            return
        self._hb_ticks += 1
        try:
            fn = getattr(self.app_core, "_update_signals_from_preview", None)
            if callable(fn):
                fn(time.time())
        except Exception:
            pass

    def _snapshot_now(self) -> None:
        self._refresh_status(force_log=True)
        try:
            sb = getattr(self.app_core, 'signal_bus', None)
            snap = sb.snapshot() if sb is not None and hasattr(sb,'snapshot') else None
            sigs = dict(getattr(snap,'signals',{}) or {}) if snap is not None else {}
            v1 = sigs.get('time.square1hz', None)
            v2 = sigs.get('time.square1hz_inv', None)
            self._log(f"[SignalProbe] time.square1hz={v1} time.square1hz_inv={v2}")
            try:
                e2 = getattr(self.app_core, '_signal_bus_update_error', None)
                if e2:
                    self._log(f"[SignalBusError] {str(e2).splitlines()[-1]}")
            except Exception:
                pass
        except Exception:
            pass

    def _refresh_status(self, force_log: bool = False) -> None:
        # Phase6 + rules status
        fired = []
        errors = []
        last_eval = None
        try:
            fired = list(getattr(self.app_core, "_rules_last_fired_ids", []) or [])
        except Exception:
            fired = []
        try:
            errors = list(getattr(self.app_core, "_rules_last_errors", []) or [])
        except Exception:
            errors = []
        try:
            last_eval = float(getattr(self.app_core, "_rules_last_eval_t", 0.0))
        except Exception:
            last_eval = 0.0

        phase6_running = "RUNNING" if self._heartbeat_enabled else "IDLE"
        self.lbl_phase6.setText(f"Phase6: {phase6_running}")

        if fired:
            self.lbl_rules.setText(f"Rules: FIRING ({len(fired)})")
        else:
            self.lbl_rules.setText("Rules: idle")

        if errors:
            self.lbl_rules.setStyleSheet("QLabel { padding: 3px 8px; border-radius: 9px; background: #400; color: #fff; }")
        else:
            self.lbl_rules.setStyleSheet("QLabel { padding: 3px 8px; border-radius: 9px; background: #222; color: #ddd; }")

        # Preview sync: reflect dirty flag / last rebuild time if available
        try:
            dirty = bool(getattr(self.app_core, "_preview_dirty", False))
        except Exception:
            dirty = False
        self.lbl_preview.setText("Preview Sync: DIRTY" if dirty else "Preview Sync: OK")

        # SurfaceSpec hash (best-effort)
        try:
            geom = getattr(self.app_core, "_full_preview_geom", None)
            h = hex(id(geom))[-6:] if geom is not None else "—"
        except Exception:
            h = "—"
        self.lbl_surface.setText(f"SurfaceSpec: {h}")

        # Parity placeholder (will be upgraded to real hash compare probe)
        self.lbl_export.setText("Parity: (use probes)")

        fired_s = ",".join(fired[:6]) + ("…" if len(fired) > 6 else "")
        self.lbl_hb_detail.setText(f"tick: {self._hb_ticks}   last_eval: {last_eval:.3f}   last_fired: {fired_s or '—'}")

        if force_log:
            self._log(f"[Snapshot] hb_ticks={self._hb_ticks} last_eval={last_eval:.3f} fired={fired} errors={len(errors)} dirty={dirty}")
            try:
                sb_err = getattr(self.app_core, '_signal_bus_update_error', None)
                if sb_err:
                    self._log('[SignalBusError] ' + str(sb_err).splitlines()[-1])
            except Exception:
                pass
            try:
                rx = getattr(self.app_core, '_rules_exception', None)
                if rx:
                    self._log('[RulesException] ' + str(rx).splitlines()[-1])
            except Exception:
                pass
            if errors:
                for e in errors[:8]:
                    self._log(f"[RuleError] {e}")

            # ---- Guided diagnostics ----

    def _guided_goal_changed(self, idx: int) -> None:
        try:
            if idx <= 0:
                self.lbl_next.setText("Next: run triage to get guided recommendations.")
                return
            goal = str(self.cmb_goal.currentText())
            self._log(f"\n[Guided] Goal selected: {goal}")
            self._log("[Guided] Tip: Click 'Run Triage' first. Follow the first non-OPEN domain and its suggested next action before running extra probes.")
        except Exception:
            pass

    def _clear_recommendations(self) -> None:
        # Remove highlight from known buttons
        try:
            btns = [
                getattr(self, 'btn_hb', None),
                getattr(self, 'btn_snapshot', None),
            ]
            # group probe buttons might not exist as attributes; ignore
            for b in btns:
                if b is not None:
                    b.setStyleSheet("")
        except Exception:
            pass

    def _recommend(self, msg: str) -> None:
        try:
            self.lbl_next.setText(msg)
        except Exception:
            pass

    def _run_quick_triage(self) -> None:
        """Run a fast, opinionated triage that tells the user exactly what to do next."""
        self._log("\n=== QUICK TRIAGE ===")
        self._clear_recommendations()

        core = getattr(self, 'app_core', None)
        fn = getattr(core, '_update_signals_from_preview', None) if core is not None else None
        if not callable(fn):
            self._log("FAIL: Phase6 tick function missing: CoreBridge._update_signals_from_preview")
            self._recommend("Core wiring issue: Phase6 tick function missing.")
            return

        # Run a short tick burst (does not depend on preview widget).
        start = time.time()
        last = start
        for _ in range(60):  # ~3 seconds at 20Hz
            now = time.time()
            fn(now)
            time.sleep(0.05)
            last = now

        # Collect observations
        phase6_ok = True
        fired = []
        errs = []
        try:
            fired = list(getattr(core, '_rules_last_fired_ids', []) or [])
        except Exception:
            fired = []
        try:
            errs = list(getattr(core, '_rules_last_errors', []) or [])
        except Exception:
            errs = []
        try:
            last_eval = float(getattr(core, '_rules_last_eval_t', 0.0) or 0.0)
        except Exception:
            last_eval = 0.0

        self._log(f"Phase6: OK (tick burst ran). last_eval_t={last_eval:.3f}")
        if errs:
            self._log("Rules: ERRORS detected:")
            for e in errs[:5]:
                self._log(f"  - {e}")

        if fired:
            self._log(f"Rules: fired ids (last eval): {fired}")
        else:
            self._log("Rules: no fired ids observed (may mean: no rules, conditions false, or time signals not updating).")

        # Check time signals presence (best-effort)
        sig_ok = None
        try:
            sb = getattr(core, 'signal_bus', None)
            snap = sb.snapshot() if sb is not None and hasattr(sb, 'snapshot') else None
            signals = dict(getattr(snap, 'signals', {}) or {}) if snap is not None else {}
            sig_ok = ('time.square1hz' in signals) or ('time.t' in signals)
            if sig_ok:
                self._log("Signals: OK (time.* present in signal bus snapshot).")
            else:
                self._log("Signals: MISSING (no time.* signals found in snapshot).")
        except Exception:
            self._log("Signals: UNKNOWN (could not snapshot signal bus).")

        # Preview dirty flag observation
        try:
            pd = bool(getattr(core, '_preview_dirty', False))
            self._log(f"Preview sync: preview_dirty={pd}")
        except Exception:
            self._log("Preview sync: UNKNOWN")

        # Recommendations (opinionated)
        goal_idx = 0
        try:
            goal_idx = int(self.cmb_goal.currentIndex())
        except Exception:
            goal_idx = 0

        if sig_ok is False:
            self._recommend("Next: open Signals tab and verify time signals are enabled; then run 'Snapshot Now' to confirm. (We will add an auto-fix soon.)")
        elif (not fired) and goal_idx in (2, 1, 5):  # rules / preview / layer controls
            self._recommend("Next: Click 'Snapshot Now' (captures project + rules state). Then run 'Layer Wiring Inspector'.")
        else:
            self._recommend("Next: run Triage. Then inspect the first non-OPEN domain.")

        try:
            self._log("--- TRIAGE ---")
            triage = self._probe_triage()
            if triage:
                self._log(triage)
        except Exception as e:
            self._log(f"[Triage] ERROR: {e}")
