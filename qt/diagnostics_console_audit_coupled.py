from __future__ import annotations

import time
import json
import hashlib
from typing import Callable, Optional

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from app.project_model import get_surface_snapshot


def _legacy_layer_param_mirror_keys() -> tuple[str, ...]:
    return (
        "layer_enabled",
        "layer_opacity",
        "layer_blend_mode",
        "layer_order",
    )

class DiagnosticsConsoleAuditCoupledMixin:
        def _coupled_suite_run_and_check(self) -> tuple[bool, dict]:
            """Coupled composition + temporal coherency."""
            self._audit_force_heartbeat()
            details = {"checks": []}

            l0 = {"name": "GREEN", "enabled": True, "opacity": 1.0, "blend_mode": "over", "order": 0,
                  "behavior": "solid", "params": {"color": [0, 255, 0]}}
            l1 = {"name": "RED", "enabled": True, "opacity": 1.0, "blend_mode": "add", "order": 1,
                  "behavior": "solid", "params": {"color": [255, 0, 0]}}

            # C1 enabled dominates
            rules = [
                self._audit_rule_tick("c1_dis", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(1, "enabled", 0)),
                self._audit_rule_tick("c1_en", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "enabled", 1)),
                self._audit_rule_tick("c1_op_inv", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(1, "opacity", 1.0)),
                self._audit_rule_tick("c1_op_sq", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "opacity", 1.0)),
                self._audit_rule_tick("c1_bm_inv", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(1, "blend_mode", "add")),
                self._audit_rule_tick("c1_bm_sq", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "blend_mode", "add")),
            ]
            self._audit_inject_project(layers=[l0, l1], rules=rules)
            if not self._audit_wait_for_fired('c1_dis', 3000):

                return False, {"summary": "C1/A sync timeout: c1_dis did not fire", "state": self._audit_capture_state(), **details}
            if not self._audit_wait_for_layer_field(1, 'enabled', False, 3000):
                return False, {"summary": "C1/A sync timeout: enabled=false did not propagate to project+preview", "state": self._audit_capture_state(), **details}
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (0, 255, 0)
            okA = st["sample"] and expA in st["sample"]
            details["checks"].append({"id": "C1/A", "expected": expA, "got": st, "ok": okA})
            if not okA:
                return False, {"summary": "C1/A expected GREEN (disabled dominates)", "state": self._audit_capture_state(), **details}

            # NOTE: This is C1/B; wait for c1_en (not a T4 id). A previous typo here caused false timeouts.
            if not self._audit_wait_for_fired('c1_en', 3000):

                return False, {"summary": "C1/B sync timeout: c1_en did not fire", "state": self._audit_capture_state(), **details}
            if not self._audit_wait_for_layer_field(1, 'enabled', True, 3000):
                return False, {"summary": "C1/B sync timeout: enabled=true did not propagate to project+preview", "state": self._audit_capture_state(), **details}
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (255, 255, 0)
            okB = st["sample"] and expB in st["sample"]
            details["checks"].append({"id": "C1/B", "expected": expB, "got": st, "ok": okB})
            if not okB:
                return False, {"summary": "C1/B expected YELLOW (enabled + add)", "state": self._audit_capture_state(), **details}

            # C2 same-field conflict determinism
            l1o = dict(l1)
            l1o["blend_mode"] = "over"
            rules = [
                self._audit_rule_tick("c2_inv_low", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(1, "opacity", 0.1)),
                self._audit_rule_tick("c2_sq_first", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "opacity", 0.2)),
                self._audit_rule_tick("c2_sq_second", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "opacity", 0.8)),
            ]
            self._audit_inject_project(layers=[l0, l1o], rules=rules)
            if not self._audit_wait_for_fired('c2_inv_low', 3000):

                return False, {"summary": "Sync timeout: c2_inv_low did not fire", **details}
            if not self._audit_wait_for_layer_field(1, 'opacity', 0.1, 3000):
                return False, {"summary": "C2/A sync timeout: opacity=0.1 did not propagate to project+preview", "state": self._audit_capture_state(), **details}
            st = self._audit_frame_stats(self._audit_render_frame())
            expA = (25, 229, 0)
            okA = st["sample"] and expA in st["sample"]
            details["checks"].append({"id": "C2/A", "expected": expA, "got": st, "ok": okA})
            if not okA:
                return False, {"summary": "C2/A expected low-opacity over sample", **details}

            if not self._audit_wait_for_fired('c2_sq_second', 3000):


                return False, {"summary": "Sync timeout: c2_sq_second did not fire", **details}
            if not self._audit_wait_for_layer_field(1, 'opacity', 0.8, 3000):
                return False, {"summary": "C2/B sync timeout: opacity=0.8 did not propagate to project+preview", "state": self._audit_capture_state(), **details}
            st = self._audit_frame_stats(self._audit_render_frame())
            expB = (204, 50, 0)
            okB = st["sample"] and expB in st["sample"]
            details["checks"].append({"id": "C2/B", "expected": expB, "got": st, "ok": okB})
            if not okB:
                return False, {"summary": "C2/B expected deterministic last-wins opacity=0.8", **details}

            # C3 temporal coherency: trail must retain red history after order flip.
            rules = [
                self._audit_rule_tick("c3_inv_o0", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(0, "order", 0)),
                self._audit_rule_tick("c3_inv_o1", "time.square1hz_inv", ">", 0.5, self._audit_action_layer_param(1, "order", 1)),
                self._audit_rule_tick("c3_sq_o0", "time.square1hz", ">", 0.5, self._audit_action_layer_param(0, "order", 1)),
                self._audit_rule_tick("c3_sq_o1", "time.square1hz", ">", 0.5, self._audit_action_layer_param(1, "order", 0)),
                self._audit_rule_tick("c3_tr_on", "time.square1hz", ">", 0.5, {"type": "set_project_field", "field": "postfx.trail_amount", "value": 0.85}),
                self._audit_rule_tick("c3_tr_on2", "time.square1hz_inv", ">", 0.5, {"type": "set_project_field", "field": "postfx.trail_amount", "value": 0.85}),
            ]
            self._audit_inject_project(layers=[l0, l1o], rules=rules, postfx={"trail_amount": 0.85})

            # Deterministic phase alignment:
            # Sample A during the *inv* phase where RED has higher order (on top).
            # Without this sync, the wallclock square wave can start in either phase
            # and produce a false failure (GREEN on top).
            if not self._audit_wait_for_fired('c3_inv_o1', 3000):
                return False, {"summary": "C3/A sync timeout: c3_inv_o1 did not fire", "state": self._audit_capture_state(), **details}
            if not self._audit_wait_for_layer_field(0, 'order', 0, 3000) or not self._audit_wait_for_layer_field(1, 'order', 1, 3000):
                return False, {"summary": "C3/A sync timeout: order inv phase did not propagate to project+preview", "state": self._audit_capture_state(), **details}

            # Deterministic temporal baseline for C3/A:
            # this suite expects the first sampled frame with trail ON to show the current
            # top layer (RED) cleanly, not stale history accumulated by incidental preview
            # renders while the audit was waiting for phase alignment. Clear only the audit
            # project's PostFX cache, then render once to seed a fresh RED history frame.
            try:
                import preview.preview_engine as _pe_mod
                pe = getattr(self.app_core, 'preview_engine', None) or getattr(self.app_core, '_full_preview_engine', None)
                proj = getattr(pe, 'project', None) if pe is not None else getattr(self.app_core, 'project', None)
                if proj is not None:
                    k = _pe_mod._postfx_project_key(proj)
                    _pe_mod._PROJECT_POSTFX_CACHE.pop(k, None)
            except Exception:
                pass
            _ = self._audit_render_frame()  # seed clean RED history for the current inv phase
            self._audit_wait(80)
            stA = self._audit_frame_stats(self._audit_render_frame())
            expA = (255, 0, 0)
            okA = stA["sample"] and expA in stA["sample"]
            details["checks"].append({"id": "C3/A", "expected": expA, "got": stA, "ok": okA})
            if not okA:
                return False, {"summary": "C3/A expected RED on top with trail ON", **details}

            # Now sync to the square phase where the order flips, then sample immediately after.
            if not self._audit_wait_for_fired('c3_sq_o1', 3000):
                return False, {"summary": "C3/B sync timeout: c3_sq_o1 did not fire", "state": self._audit_capture_state(), **details}
            if not self._audit_wait_for_layer_field(0, 'order', 1, 3000) or not self._audit_wait_for_layer_field(1, 'order', 0, 3000):
                return False, {"summary": "C3/B sync timeout: order sq phase did not propagate to project+preview", "state": self._audit_capture_state(), **details}

            _ = self._audit_render_frame()  # prime the trail buffer
            self._audit_wait(80)
            stB = self._audit_frame_stats(self._audit_render_frame())
            mixed_ok = False
            if stB["sample"]:
                for c in stB["sample"]:
                    try:
                        r, g, b = c
                        if r > 0 and g > 0 and b == 0:
                            mixed_ok = True
                            break
                    except Exception:
                        pass
            details["checks"].append({"id": "C3/B", "expected": "MIXED (r>0,g>0)", "got": stB, "ok": mixed_ok})
            if not mixed_ok:
                return False, {"summary": "C3/B expected trail history (mixed frame) after order flip; likely temporal state reset on rebuild", **details}

            return True, details
