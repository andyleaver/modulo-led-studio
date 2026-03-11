"""Qt application entrypoint.

This file is intentionally small and stable.
UI composition lives in:
  - qt/main_window.py (QtMainWindow shell)
  - qt/main_layout.py (window layout)
  - qt/tab_registry.py (tabs + order)
"""

from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None


def _diag_exc(e: Exception, where: str) -> None:
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_APP_EXCEPTION", summary=where)
    except Exception:
        pass

# Safe logging
import sys as _sys, traceback as _traceback, time as _time
from pathlib import Path as _Path
import os
import sys


def _read_app_id() -> str:
    """Read APP_ID.txt from the repo root (same folder as RUN.sh)."""
    try:
        here = os.path.abspath(os.path.dirname(__file__))
        root = os.path.abspath(os.path.join(here, os.pardir))
        bid_path = os.path.join(root, "APP_ID.txt")
        with open(bid_path, "r", encoding="utf-8") as f:
            bid = f.read().strip()
        return bid or "DEV"
    except Exception:
        return "DEV"


APP_ID = _read_app_id()


def _install_global_excepthook(app_name: str = "Modulo"):
    """Show a fatal error dialog instead of silently closing on uncaught exceptions."""
    try:
        from qt.qt_compat import QtWidgets  # type: ignore
    except Exception:
        try:
            from qt.qt_compat import QtWidgets  # type: ignore
        except Exception:
            QtWidgets = None  # type: ignore

    def _hook(exctype, value, tb):
        try:
            import traceback as _tb
            msg = "".join(_tb.format_exception(exctype, value, tb))
        except Exception:
            msg = f"{exctype.__name__}: {value}"

        try:
            sys.stderr.write(msg + "\n")
        except Exception as e:
            _diag_exc(e, "qt_app")

        try:
            if QtWidgets is not None and QtWidgets.QApplication.instance() is not None:
                QtWidgets.QMessageBox.critical(
                    None,
                    f"{app_name} — Fatal Error",
                    "An unexpected error occurred.\n\n" + msg[-4000:],
                )
        except Exception as e:
            _diag_exc(e, "qt_app")

    sys.excepthook = _hook


def run_qt(app_core, argv=None):
    """Launch the Qt UI."""
    argv = list(argv) if argv is not None else sys.argv

    _install_global_excepthook("Modulo")

    # Qt imports
    try:
        from qt.qt_compat import QtWidgets  # type: ignore
    except Exception:
        from qt.qt_compat import QtWidgets  # type: ignore

    from qt.main_window import QtMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv)

    # Build + show
    win = QtMainWindow(app_core)
    try:
        # Expose APP_ID to layout helpers
        win.APP_ID = APP_ID
    except Exception as e:
        _diag_exc(e, "qt_app")

    win.show()

    # Run event loop
    return app.exec()
