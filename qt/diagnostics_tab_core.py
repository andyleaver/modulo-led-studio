from __future__ import annotations

import json

from qt.diagnostics_tab_helpers import project_data, runtime_data

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(error: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(error, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass


class DiagnosticsTabCoreMixin:
    def _set_probe_text(self, text: str):
        """Write probe text to all visible diagnostics output widgets."""
        rendered = str(text)
        wrote = False
        for name in ("probe_output", "out", "output"):
            try:
                w = getattr(self, name, None)
            except Exception:
                w = None
            if w is None:
                continue
            try:
                w.setPlainText(rendered)
                wrote = True
            except Exception:
                pass
        if not wrote:
            print(rendered)

    def _diag_set(self, msg: str):
        try:
            self._set_probe_text(msg)
        except Exception as e:
            _diag_exc(e, "qt/diagnostics_tab.py")
            print(msg)

    def _diag_bump(self, tag: str):
        try:
            self._diag_set(f"{tag}: CLICKED\n")
        except Exception as e:
            _diag_exc(e, "qt/diagnostics_tab.py")

    def _safe_json(self, obj) -> str:
        try:
            return json.dumps(obj, indent=2, sort_keys=False)
        except Exception:
            try:
                return str(obj)
            except Exception:
                return "<unprintable>"

    def _runtime_data(self):
        value = runtime_data(self.app_core, self.controller)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = {}
        return value if isinstance(value, dict) else {}

    def _project_data(self):
        return project_data(self.app_core, self.controller)
