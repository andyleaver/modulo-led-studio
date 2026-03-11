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

def restore_splitter(splitter: QtWidgets.QSplitter, key: str):
    try:
        settings = QtCore.QSettings()
        val = settings.value(key, None)
        if val is None:
            return
        if isinstance(val, (bytes, bytearray)):
            splitter.restoreState(bytes(val))
        elif isinstance(val, str):
            # QSettings can return base64 string
            try:
                splitter.restoreState(QtCore.QByteArray.fromBase64(val.encode("utf-8")))
            except Exception as e:
                _diag_exc(e, "qt/splitters.py")
    except Exception as e:
        _diag_exc(e, "qt/splitters.py")

def save_splitter(splitter: QtWidgets.QSplitter, key: str):
    try:
        settings = QtCore.QSettings()
        settings.setValue(key, splitter.saveState())
    except Exception as e:
        _diag_exc(e, "qt/splitters.py")
