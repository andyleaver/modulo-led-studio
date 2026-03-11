from __future__ import annotations

from qt.qt_compat import QtWidgets
from qt.wiretap_log_panel import WiretapLogPanel
from qt.wiretap_manager import WiretapManager
from qt.wiretap_support import set_log_panel


def install_wiretap(main_window: QtWidgets.QMainWindow) -> WiretapManager:
    wiretap = WiretapManager(main_window)
    wiretap.install_signal_probes()
    wiretap._install_notify_hook()
    return wiretap


def dump_ui_layout_strip_preview(main_window=None) -> str:
    try:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return "[DumpUI] QApplication not running"
        wins = [w for w in app.topLevelWidgets() if w.isVisible()]
        if main_window is None:
            main_window = wins[0] if wins else None
        if main_window is None:
            return "[DumpUI] No visible top-level window"
        from qt.wiretap_log_panel import dump_interactive_widgets
        return dump_interactive_widgets(main_window)
    except Exception as exc:
        return f"[DumpUI] ERROR: {exc}"
