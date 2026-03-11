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



class DiagnosticsConsoleDoorsUtilityMixin:
    def _project_fingerprint(self) -> tuple[str, dict]:
        """Stable fingerprint of *authored project state*.

        This MUST NOT include runtime-only fields (timers, caches, counters, rule cadence state, buffers),
        otherwise fingerprints will change even when the authored project did not.
        """
        core = getattr(self, "app_core", None)
        payload: dict = {}
        proj_dict = None
        try:
            proj = getattr(core, "project", None)
            if isinstance(proj, dict):
                proj_dict = proj
            elif hasattr(proj, "to_dict"):
                proj_dict = proj.to_dict()  # type: ignore
        except Exception:
            proj_dict = None

        if isinstance(proj_dict, dict):
            # Remove obvious volatile keys if present.
            volatile = {
                # timestamps / ids
                "last_saved", "saved_at", "timestamp", "ts", "created_at", "updated_at",
                "project_id", "uuid", "session_id", "run_id",
                # build / diagnostics
                "app_id", "diagnostics", "_diagnostics",
            }
            cleaned = {}
            for k, v in proj_dict.items():
                if str(k) in volatile:
                    continue
                cleaned[k] = v
            payload["project"] = cleaned
        else:
            payload["project"] = None
        try:
            s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        except Exception:
            s = repr(payload)
        h = hashlib.sha1(s.encode("utf-8")).hexdigest()
        return h, payload

    def _shallow_dict_diff(self, a: dict, b: dict) -> dict:
        """Return a small diff summary for two dicts (top-level only)."""
        out = {"added": [], "removed": [], "changed": []}
        try:
            ak = set(a.keys())
            bk = set(b.keys())
            out["added"] = sorted(list(bk - ak))
            out["removed"] = sorted(list(ak - bk))
            for k in sorted(list(ak & bk)):
                if a.get(k) != b.get(k):
                    out["changed"].append(k)
        except Exception:
            pass
        return out

    def _with_clean_diagnostics_sandbox(self, fn):
        # Clean sandbox: blank PreviewEngine state every run; restore project after.
        import copy
        core = getattr(self, 'app_core', None)
        if core is None:
            return fn()
        try:
            proj_snapshot = copy.deepcopy(getattr(core, 'project', None))
        except Exception:
            proj_snapshot = None
        try:
            if hasattr(core, 'rebuild_preview_clean'):
                core.rebuild_preview_clean('diagnostics_pre')
            else:
                core.rebuild_preview()
        except Exception:
            pass

        # IMPORTANT: Some doors (notably J1) drive synthetic timestamps into the rules engine.
        # If we don't reset these, later runs can see (tt - last_apply) < 0 and rules will not
        # evaluate, producing "passes once, fails forever" behavior.
        try:
            setattr(core, '_rules_last_apply_t', 0.0)
        except Exception:
            pass
        try:
            setattr(core, '_rules_prev_state', {})
        except Exception:
            pass
        try:
            setattr(core, '_rules_last_fired_ids', [])
        except Exception:
            pass
        try:
            setattr(core, '_rules_last_errors', [])
        except Exception:
            pass
        try:
            return fn()
        finally:
            try:
                if proj_snapshot is not None:
                    core.project = proj_snapshot
            except Exception:
                pass
            try:
                if hasattr(core, 'rebuild_preview_clean'):
                    core.rebuild_preview_clean('diagnostics_post')
                else:
                    core.rebuild_preview()
            except Exception:
                pass
            try:
                core.update_all()
            except Exception:
                pass

    def _set_audit_busy(self, busy: bool, why: str = "") -> None:
        """Disable re-entrancy for diagnostics runs.

        Users can click RUN again while a run is already executing, which can corrupt
        shared state and create forced failures. Keep diagnostics single-flight.
        """
        try:
            setattr(self, "_audit_running", bool(busy))
        except Exception:
            pass

        try:
            if why:
                self.lbl_audit_summary.setText(why)
        except Exception:
            pass

        widgets = []
        for name in ("btn_run_probe", "chk_clean_each", "spn_repeat", "cmb_probe"):
            try:
                w = getattr(self, name, None)
                if w is not None:
                    widgets.append(w)
            except Exception:
                pass

        for w in widgets:
            try:
                w.setEnabled(not busy)
            except Exception:
                pass

