
from __future__ import annotations

try:
    from qt.qt_compat import QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtWidgets  # type: ignore

from qt.diagnostics_tab_actions import DiagnosticsTabActionsMixin
from qt.diagnostics_tab_core import DiagnosticsTabCoreMixin
from qt.diagnostics_tab_probes import DiagnosticsTabProbeMixin
from qt.diagnostics_console_audit import DiagnosticsConsoleAuditMixin
from qt.diagnostics_console_doors_probes import DiagnosticsConsoleDoorsProbeMixin
from qt.diagnostics_tab_ui import build_diagnostics_tab_ui


class DiagnosticsTab(
    QtWidgets.QWidget,
    DiagnosticsTabCoreMixin,
    DiagnosticsTabActionsMixin,
    DiagnosticsConsoleAuditMixin,
    DiagnosticsConsoleDoorsProbeMixin,
    DiagnosticsTabProbeMixin,
):
    def __init__(self, app_core, controller=None):
        super().__init__()
        self.app_core = app_core
        self.controller = controller
        self._heartbeat_enabled = False
        self._hb_ticks = 0
        try:
            from qt.qt_compat import QtCore  # type: ignore
            self._hb_timer = QtCore.QTimer(self)
            self._hb_timer.setInterval(50)
        except Exception:
            self._hb_timer = None
        build_diagnostics_tab_ui(self)
