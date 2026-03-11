from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
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
    from qt.qt_compat import QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtWidgets  # type: ignore

def set_window_title(window, app_id: str):
    try:
        title = "Modulo LED Studio"
        if app_id:
            title += f" — {app_id}"
        window.setWindowTitle(title)
    except Exception as e:
        _diag_exc(e, "qt/window_chrome.py")

def ensure_status_bar(window):
    try:
        if window.statusBar() is None:
            window.setStatusBar(QtWidgets.QStatusBar())
    except Exception as e:
        _diag_exc(e, "qt/window_chrome.py")
