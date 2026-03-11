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

from qt.qt_compat import QtCore

QTimer = QtCore.QTimer

from qt.era_panel_workbench_state import EraPanelWorkbenchStateMixin
from qt.era_panel_workbench_preview import EraPanelWorkbenchPreviewMixin
from qt.era_panel_workbench_flow import EraPanelWorkbenchFlowMixin


class EraPanelWorkbenchMixin(
    EraPanelWorkbenchStateMixin,
    EraPanelWorkbenchPreviewMixin,
    EraPanelWorkbenchFlowMixin,
):
    pass
