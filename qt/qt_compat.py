"""Qt binding compatibility layer.

Prefers PySide6/PyQt6 when available, but supports PyQt5/PySide2 for environments
where newer bindings aren't installed.
"""

from __future__ import annotations

QtCore = None
QtGui = None
QtWidgets = None

# Order matters: prefer modern bindings, but fall back to what is commonly installed.
_BINDINGS = ("PySide6", "PyQt6", "PyQt5", "PySide2")

_last_err: Exception | None = None
for _b in _BINDINGS:
    try:
        if _b == "PySide6":
            from PySide6 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # type: ignore
        elif _b == "PyQt6":
            from PyQt6 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # type: ignore
        elif _b == "PyQt5":
            from PyQt5 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # type: ignore
        elif _b == "PySide2":
            from PySide2 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # type: ignore
        QtCore, QtGui, QtWidgets = _QtCore, _QtGui, _QtWidgets
        break
    except Exception as e:  # pragma: no cover
        _last_err = e

if QtCore is None or QtGui is None or QtWidgets is None:  # pragma: no cover
    raise ModuleNotFoundError(
        "No supported Qt binding found. Install one of: PySide6, PyQt6, PyQt5, PySide2"
    ) from _last_err

# Unify Signal/Slot across bindings.
Signal = getattr(QtCore, "Signal", getattr(QtCore, "pyqtSignal", None))
Slot = getattr(QtCore, "Slot", getattr(QtCore, "pyqtSlot", None))
Property = getattr(QtCore, "Property", getattr(QtCore, "pyqtProperty", None))
