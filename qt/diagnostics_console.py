from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtCore, QtWidgets  # type: ignore
from qt.diagnostics_console_build import build_diagnostics_console_ui
from qt.diagnostics_console_probes import DiagnosticsConsoleProbeMixin
from qt.diagnostics_console_doors import DiagnosticsConsoleDoorsMixin
from qt.diagnostics_console_audit import DiagnosticsConsoleAuditMixin


class DiagnosticsConsole(
    DiagnosticsConsoleProbeMixin,
    DiagnosticsConsoleDoorsMixin,
    DiagnosticsConsoleAuditMixin,
    QtWidgets.QDockWidget,
):
    """Dockable diagnostics console with a single canonical runner surface."""

    def __init__(self, app_core, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Diagnostics Console", parent)
        self.setObjectName("diagnostics_console")
        self.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
            | QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
            | QtCore.Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.app_core = app_core
        self._heartbeat_enabled = False
        self._hb_ticks = 0
        build_diagnostics_console_ui(self)
