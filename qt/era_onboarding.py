from __future__ import annotations

try:
    from PySide6 import QtWidgets, QtCore  # type: ignore
except Exception:  # pragma: no cover
    from PyQt6 import QtWidgets, QtCore  # type: ignore

from qt.era_panel import EraPanel

# Qt binding compatibility (PySide6 uses QtCore.Signal; PyQt6 uses QtCore.pyqtSignal)
_Signal = getattr(QtCore, 'Signal', None) or getattr(QtCore, 'pyqtSignal', None)
if _Signal is None:  # pragma: no cover
    raise ImportError('QtCore Signal/pyqtSignal not found')



class EraOnboardingWindow(QtWidgets.QMainWindow):
    """Full-screen Era onboarding mode.

    While active, the rest of the application UI is not shown.
    When the final era is completed, this window emits `completed`.
    """

    completed = _Signal()

    def __init__(self, app_core, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self.setWindowTitle("Modulo — LED Era System")

        self._panel = EraPanel(app_core)
        self._panel.era_completed.connect(self._on_completed)

        # Era content can be long (small screens / accessibility).
        # Use a scroll view so every era remains readable without forcing a huge window.
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        except Exception:
            try:
                scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            except Exception:
                pass

        root = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.addWidget(self._panel)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)

        # Keep it resizable on all platforms (do not lock to a large minimum).
        try:
            self.setMinimumSize(640, 420)
        except Exception:
            pass

    def _on_completed(self):
        self.completed.emit()
