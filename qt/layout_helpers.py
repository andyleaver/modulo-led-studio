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
import sys

# Timeless UI title (versions belong in release tags/changelog, not runtime code).
from app.project_canonical import canonicalize_project_dict
APP_TITLE = "Modulo LED Studio"

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
            _diag_exc(e, "qt/layout_helpers.py")

        try:
            if QtWidgets is not None and QtWidgets.QApplication.instance() is not None:
                QtWidgets.QMessageBox.critical(
                    None,
                    f"{app_name} — Fatal Error",
                    "An unexpected error occurred.\n\n" + msg[-4000:],
                )
        except Exception as e:
            _diag_exc(e, "qt/layout_helpers.py")

    sys.excepthook = _hook

def _normalize_project(project):
    """Best-effort project normalization.

    Route helper-side cleanup through the canonical project pipeline so layout,
    UI, targets, layers, variables, and rules all converge on one truth path.
    """
    if not isinstance(project, dict):
        return

    try:
        p2, _changes = canonicalize_project_dict(project)
        if isinstance(p2, dict) and p2 is not project:
            project.clear()
            project.update(p2)
    except Exception as e:
        _diag_exc(e, "qt/layout_helpers.py::_normalize_project")
