from __future__ import annotations

import time

from qt.qt_compat import QtCore


class DiagnosticsConsoleAuditWaitsMixin:
    def _audit_wait(self, ms: int) -> None:
        """Wait while keeping Qt responsive."""
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def _audit_wait_for_fired(self, want_id: str, timeout_ms: int = 1500) -> bool:
        """Wait until Rules reports a specific fired rule id (deterministic sync point)."""
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            try:
                fired = list(getattr(self.app_core, "_rules_last_fired_ids", []) or [])
            except Exception:
                fired = []
            if want_id in fired:
                return True
            # keep UI responsive and let heartbeat tick
            self._audit_wait(50)
        return False

    def _audit_wait_for_layer_enabled(self, layer_index: int, want_enabled: bool, timeout_ms: int = 1500) -> bool:
        """Wait until both Project dict and PreviewEngine layer reflect enabled state."""
        deadline = time.time() + (timeout_ms / 1000.0)
        li = int(layer_index)
        while time.time() < deadline:
            proj_ok = False
            pe_ok = False
            try:
                p = getattr(self.app_core, "project", {}) or {}
                ls = list(p.get("layers") or [])
                if isinstance(ls, list) and len(ls) > li and isinstance(ls[li], dict):
                    proj_ok = bool(ls[li].get("enabled", True)) == bool(want_enabled)
                if not proj_ok:
                    pm = getattr(self.app_core, "pm", None)
                    pp = getattr(pm, "project", {}) if pm is not None else {}
                    pls2 = list((pp.get("layers") or [])) if isinstance(pp, dict) else []
                    if isinstance(pls2, list) and len(pls2) > li and isinstance(pls2[li], dict):
                        proj_ok = bool(pls2[li].get("enabled", True)) == bool(want_enabled)
            except Exception:
                proj_ok = False
            try:
                pe = getattr(self.app_core, "preview_engine", None)
                pm = getattr(pe, "project", None) if pe is not None else None
                pls = list(getattr(pm, "layers", []) or []) if pm is not None else []
                if isinstance(pls, list) and len(pls) > li:
                    pe_val = getattr(pls[li], 'en', getattr(pls[li], 'enabled', True))
                    pe_ok = bool(pe_val) == bool(want_enabled)
            except Exception:
                pe_ok = False

            if proj_ok and pe_ok:
                return True
            self._audit_wait(50)
        return False

    def _audit_wait_for_layer_field(self, layer_index: int, field: str, want_value, timeout_ms: int = 1500) -> bool:
        """Wait until Project dict/PM project and PreviewEngine project agree on a canonical layer field."""
        deadline = time.time() + (timeout_ms / 1000.0)
        li = int(layer_index)
        fname = str(field or '').strip()
        while time.time() < deadline:
            proj_ok = False
            pe_ok = False
            try:
                def _matches(v):
                    if fname == 'opacity':
                        try:
                            return abs(float(v) - float(want_value)) <= 1e-6
                        except Exception:
                            return False
                    if fname == 'order':
                        try:
                            return int(v) == int(want_value)
                        except Exception:
                            return False
                    if fname == 'enabled':
                        return bool(v) == bool(want_value)
                    return str(v) == str(want_value)

                p = getattr(self.app_core, 'project', {}) or {}
                ls = list(p.get('layers') or []) if isinstance(p, dict) else []
                if isinstance(ls, list) and len(ls) > li and isinstance(ls[li], dict):
                    proj_ok = _matches(ls[li].get(fname, None))
                if not proj_ok:
                    pm = getattr(self.app_core, 'pm', None)
                    pp = getattr(pm, 'project', {}) if pm is not None else {}
                    pls2 = list((pp.get('layers') or [])) if isinstance(pp, dict) else []
                    if isinstance(pls2, list) and len(pls2) > li and isinstance(pls2[li], dict):
                        proj_ok = _matches(pls2[li].get(fname, None))
            except Exception:
                proj_ok = False
            try:
                pe = getattr(self.app_core, 'preview_engine', None)
                pm = getattr(pe, 'project', None) if pe is not None else None
                pls = list(getattr(pm, 'layers', []) or []) if pm is not None else []
                if isinstance(pls, list) and len(pls) > li:
                    lv = getattr(pls[li], fname, None)
                    pe_ok = _matches(lv)
            except Exception:
                pe_ok = False
            if proj_ok and pe_ok:
                return True
            self._audit_wait(50)
        return False

    def _audit_wait_for_pe_layers(self, min_layers: int = 2, timeout_ms: int = 1500) -> bool:
        """Wait until PreviewEngine exposes at least min_layers layers in captured state."""
        deadline = time.time() + (timeout_ms / 1000.0)
        want = int(min_layers)
        while time.time() < deadline:
            try:
                st = self._audit_capture_state()
                if len(list(st.get("pe_layers", []) or [])) >= want:
                    return True
            except Exception:
                pass
            self._audit_wait(50)
        return False


