"""Compatibility wrapper for DiagnosticsTab.

Implementation lives in qt.diagnostics_tab_impl.
"""
from __future__ import annotations

from qt.qt_compat import QtWidgets  # type: ignore

from qt.diagnostics_tab_impl import DiagnosticsTab
from qt.diagnostics_tab_ui_dump import dump_ui_layout_strip_preview

__all__ = ["DiagnosticsTab", "dump_ui_layout_strip_preview"]
