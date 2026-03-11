from __future__ import annotations

import traceback
from typing import Any

from qt.qt_compat import QtCore

_LOG_PANEL = None


def _diag_exc(exc: Exception, where: str) -> None:
    try:
        _log_line(f"[wiretap:{where}] {type(exc).__name__}: {exc}")
        _log_line(traceback.format_exc(limit=2).rstrip())
    except Exception:
        pass


def _log_line(line: str) -> None:
    global _LOG_PANEL
    try:
        if _LOG_PANEL is None:
            return
        if hasattr(_LOG_PANEL, "append_line"):
            _LOG_PANEL.append_line(str(line))
        elif hasattr(_LOG_PANEL, "appendPlainText"):
            _LOG_PANEL.appendPlainText(str(line))
    except Exception:
        pass


def set_log_panel(panel: Any) -> None:
    global _LOG_PANEL
    _LOG_PANEL = panel


def _w_text(obj: Any) -> str:
    if obj is None:
        return "<none>"
    for attr in ("text", "windowTitle", "title"):
        try:
            fn = getattr(obj, attr, None)
            value = fn() if callable(fn) else fn
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _obj_path(obj: QtCore.QObject | None) -> str:
    if obj is None:
        return "<none>"
    parts: list[str] = []
    cur: QtCore.QObject | None = obj
    while cur is not None:
        try:
            name = cur.objectName()
        except Exception:
            name = ""
        parts.append(name or cur.__class__.__name__)
        try:
            cur = cur.parent()
        except Exception:
            break
    return "/".join(reversed(parts))
