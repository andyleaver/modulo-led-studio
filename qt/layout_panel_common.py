from __future__ import annotations

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

from qt.qt_compat import QtWidgets


def diag_exc(exc: Exception, where: str) -> None:
    try:
        if _DIAGS is not None:
            _DIAGS.exception(exc, domain='UI', code='QT_UI_EXCEPTION', summary=where)
    except Exception:
        pass
