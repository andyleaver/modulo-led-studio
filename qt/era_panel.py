from __future__ import annotations

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(e: Exception, where: str) -> None:
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass


from typing import Optional, Dict, Any

from qt.qt_compat import QtCore, QtGui, QtWidgets, Signal
from app.eras.era_history import get_era, get_eras, get_phase_note, get_workbench_for_era
from app.eras.era_progression import get_active_era, get_unlocked, unlock_next, set_active, gates_for_project
from qt.era_panel_logic import EraPanelLogicMixin
from qt.era_panel_ui import build_era_panel_ui

Qt = QtCore.Qt
QTimer = QtCore.QTimer
QWidget = QtWidgets.QWidget
QPainter = QtGui.QPainter
QColor = QtGui.QColor
QPen = QtGui.QPen


class EraPanel(EraPanelLogicMixin, QWidget):
    def __init__(self, app_core, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self._display_era_id: Optional[str] = None
        self._wb_state: Dict[str, Any] = {}
        self._wb_verified: Dict[str, bool] = {}
        self._known_unlocked: list[str] = []

        build_era_panel_ui(self)
        self._populate_browse()
        self.refresh()
