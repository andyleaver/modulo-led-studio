from __future__ import annotations

try:
    from qt.qt_compat import QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtWidgets  # type: ignore

def build_targeting_tools_widget(app_core, controller=None) -> QtWidgets.QWidget:
    """Small helper widget for targeting actions.

    Kept minimal during UI breakdown. Safe to expand later.
    """
    w = QtWidgets.QGroupBox("Targeting Tools")
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 8)
    lay.setSpacing(6)

    info = QtWidgets.QLabel("Targeting helpers will appear here.")
    info.setWordWrap(True)
    lay.addWidget(info)

    return w
