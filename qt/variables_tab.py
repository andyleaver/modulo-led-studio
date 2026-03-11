try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.variables_panel import VariablesPanel

class VariablesTab(QtWidgets.QWidget):
    """Variables tab container extracted from qt_app.py."""

    def __init__(self, app_core, controller=None):
        super().__init__()
        self.app_core = app_core
        self.controller = controller

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # Header row (compact)
        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Variables"))
        hdr.addStretch(1)
        outer.addLayout(hdr)

        intro = QtWidgets.QLabel("Variables store shared state. Use them for memory, counters, and values that rules and behaviors can read.")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        self.panel = VariablesPanel(app_core)
        self._scroll = QtWidgets.QScrollArea()

        self._scroll.setWidgetResizable(True)

        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll.setWidget(self.panel)

        outer.addWidget(self._scroll, 1)
