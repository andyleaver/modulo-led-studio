from __future__ import annotations

from qt.qt_compat import QtCore, QtGui, QtWidgets


def _parent_path(widget: QtWidgets.QWidget) -> str:
    parts: list[str] = []
    cur: QtWidgets.QWidget | None = widget
    for _ in range(14):
        if cur is None:
            break
        parts.append(cur.objectName() or cur.__class__.__name__)
        cur = cur.parent()  # type: ignore[assignment]
    return " <- ".join(parts)


def _widget_desc(widget: QtWidgets.QWidget) -> str:
    cls = widget.__class__.__name__
    name = widget.objectName() or ""
    text = ""
    try:
        fn = getattr(widget, "text", None)
        if callable(fn):
            text = str(fn() or "")
    except Exception:
        text = ""
    msg = f"{cls} name='{name}'"
    if text:
        msg += f" text='{text[:80]}'"
    return msg


class WiretapPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        self.btn_test = QtWidgets.QPushButton("Wiretap Test")
        self.btn_snap_hover = QtWidgets.QPushButton("Snapshot Hover")
        self.btn_snap_focus = QtWidgets.QPushButton("Snapshot Focus")
        self.btn_dump = QtWidgets.QPushButton("Dump UI")
        self.btn_poll = QtWidgets.QPushButton("Polling: ON")
        self.btn_poll.setCheckable(True)
        self.btn_poll.setChecked(True)
        self.btn_clear = QtWidgets.QPushButton("Clear")
        for button in [self.btn_test, self.btn_snap_hover, self.btn_snap_focus, self.btn_dump, self.btn_poll, self.btn_clear]:
            header.addWidget(button, 0)
        header.addStretch(1)
        outer.addLayout(header)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        try:
            self.log.setMaximumBlockCount(4000)
        except Exception:
            pass
        font = self.log.font()
        try:
            font.setFamily("Monospace")
            font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
            self.log.setFont(font)
        except Exception:
            pass
        outer.addWidget(self.log, 1)

        self._poll_enabled = True
        self._last_focus_id = None
        self._last_hover_id = None
        self.append_line("Wiretap panel ready")
        self.append_line("Tip: press Ctrl+I to snapshot focused widget.")

        self._poll = QtCore.QTimer(self)
        self._poll.setInterval(200)
        self._poll.timeout.connect(self._poll_tick)
        self._poll.start()

        self.btn_test.clicked.connect(lambda: self.append_line("Wiretap test button clicked"))
        self.btn_clear.clicked.connect(self.log.clear)
        self.btn_dump.clicked.connect(self._dump_ui)
        self.btn_poll.toggled.connect(self._set_polling)
        self.btn_snap_hover.clicked.connect(self._snapshot_hover)
        self.btn_snap_focus.clicked.connect(self._snapshot_focus)

        try:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+I"), self)
            shortcut.activated.connect(self._snapshot_focus)
        except Exception:
            pass

    def append_line(self, line: str) -> None:
        self.log.appendPlainText(str(line))
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_polling(self, enabled: bool) -> None:
        self._poll_enabled = bool(enabled)
        self.btn_poll.setText("Polling: ON" if enabled else "Polling: OFF")
        self.append_line(f"Polling set to: {enabled}")

    def _poll_tick(self) -> None:
        if not self._poll_enabled:
            return
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        focus_widget = app.focusWidget()
        focus_id = id(focus_widget) if focus_widget is not None else None
        if focus_id != self._last_focus_id:
            self._last_focus_id = focus_id
            self.append_line("FOCUS(poll): None" if focus_widget is None else f"FOCUS(poll): {_widget_desc(focus_widget)}")
        hover_widget = app.widgetAt(QtGui.QCursor.pos())
        hover_id = id(hover_widget) if hover_widget is not None else None
        if hover_id != self._last_hover_id:
            self._last_hover_id = hover_id
            self.append_line("HOVER(poll): None" if hover_widget is None else f"HOVER(poll): {_widget_desc(hover_widget)}")

    def _snapshot_hover(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        widget = app.widgetAt(QtGui.QCursor.pos())
        if widget is None:
            self.append_line("SNAPSHOT hover: None")
            return
        self.append_line("=== SNAPSHOT HOVER ===")
        self.append_line(_widget_desc(widget))
        self.append_line("PATH: " + _parent_path(widget))
        self.append_line("=== END SNAPSHOT ===")

    def _snapshot_focus(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        widget = app.focusWidget()
        if widget is None:
            self.append_line("SNAPSHOT focus: None")
            return
        self.append_line("=== SNAPSHOT FOCUS ===")
        self.append_line(_widget_desc(widget))
        self.append_line("PATH: " + _parent_path(widget))
        self.append_line("=== END SNAPSHOT ===")

    def _dump_ui(self) -> None:
        window = self.window()
        self.append_line("=== DUMP UI (interactive widgets) ===")
        count = 0
        if window is not None:
            for widget in window.findChildren(QtWidgets.QWidget):
                if isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QComboBox, QtWidgets.QAbstractSlider,
                                       QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QLineEdit)):
                    self.append_line("- " + _widget_desc(widget))
                    count += 1
                    if count >= 350:
                        self.append_line("... (truncated)")
                        break
        self.append_line(f"=== END DUMP (count={count}) ===")


class WiretapLogPanel(WiretapPanel):
    pass


def dump_interactive_widgets(main_window: QtWidgets.QWidget) -> str:
    out = ["=== UI LAYOUT DUMP (interactive widgets) ==="]
    count = 0
    for widget in main_window.findChildren(QtWidgets.QWidget):
        if isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QComboBox, QtWidgets.QAbstractSlider,
                               QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QLineEdit)):
            out.append("- " + _widget_desc(widget))
            count += 1
            if count >= 350:
                out.append("... (truncated)")
                break
    out.append(f"=== END DUMP (count={count}) ===")
    return "\n".join(out)
