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
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

def wrap_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Wrap a widget in a QScrollArea so large panels remain usable on small windows."""
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    try:
        sa.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    except Exception:
        try:
            sa.setFrameShape(QtWidgets.QFrame.NoFrame)
        except Exception as e:
            _diag_exc(e, "qt/scroll_wrap.py")
    try:
        sa.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sa.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    except Exception:
        # PyQt6 fallback
        try:
            sa.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            sa.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        except Exception as e:
            _diag_exc(e, "qt/scroll_wrap.py")

    sa.setWidget(widget)
    return sa
