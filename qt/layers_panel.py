from __future__ import annotations

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass

try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

import copy
import time as _time

from runtime.resolver import set_address
from params.registry import PARAMS
from params.ensure import ensure_params
from behaviors.registry import get_effect
from qt.layers_panel_actions import LayersPanelActionsMixin
from qt.layers_panel_ui import build_layers_panel_ui

class LayersPanel(LayersPanelActionsMixin, QtWidgets.QWidget):
    def __init__(self, app_core, controller=None):
            super().__init__()
            self.app_core = app_core
            self.controller = controller

            build_layers_panel_ui(self)

            self._populate_effects()
            self.refresh()

