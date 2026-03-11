from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtCore, QtGui, QtWidgets
from qt.wiretap_overlay import WiretapOverlay
from qt.wiretap_support import _diag_exc, _log_line, _obj_path, _w_text


class WiretapManager(QtCore.QObject):
    """Captures UI interactions and reports wiring state immediately."""

    def __init__(self, main_window: QtWidgets.QMainWindow):
        super().__init__(main_window)
        self.main_window = main_window
        self.enabled = True
        self.overlay = WiretapOverlay(main_window)
        self.overlay.setGeometry(main_window.rect())
        self.overlay.show()
        self._installed = False
        self._signal_tap_installed = False
        self._tap_watchdog: QtCore.QTimer | None = None

        main_window.installEventFilter(self)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        _log_line("Wiretap: installed")
        QtCore.QTimer.singleShot(0, self._ensure_global_filters)
        QtCore.QTimer.singleShot(250, self._ensure_global_filters)
        self._start_signal_tap_watchdog()

    def _emit(self, msg: str, *, ttl: float = 2.5) -> None:
        self.overlay.show_msg(msg, ttl=ttl)

    def eventFilter(self, obj, event):  # noqa: N802
        try:
            if obj is self.main_window and event.type() == QtCore.QEvent.Type.Resize:
                self.overlay.setGeometry(self.main_window.rect())

            if not self.enabled:
                return False

            event_type = event.type()
            if event_type in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
                widget = obj if isinstance(obj, QtWidgets.QWidget) else None
                if widget is None or widget is self.overlay:
                    return False
                phase = "press" if event_type == QtCore.QEvent.Type.MouseButtonPress else "release"
                self._emit(f"MOUSE({phase}): {widget.__class__.__name__} name='{widget.objectName() or ''}'", ttl=1.2)
                self._report_click(widget)
            return False
        except Exception as exc:
            _diag_exc(exc, "wiretap.eventFilter")
            return False

    def _ensure_global_filters(self) -> None:
        self._install_notify_hook()
        self._install_focus_hook()
        self._tap_signals()

    def _install_notify_hook(self) -> None:
        try:
            app = QtWidgets.QApplication.instance()
            if app is None or getattr(app, "_wiretap_notify_wrapped", False):
                return
            original_notify = app.notify

            def notify(receiver, event):  # type: ignore[override]
                try:
                    et = event.type()
                    if et in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
                        widget = receiver if isinstance(receiver, QtWidgets.QWidget) else None
                        if widget is not None and widget is not self.overlay:
                            phase = "press" if et == QtCore.QEvent.Type.MouseButtonPress else "release"
                            self._emit(f"NOTIFY_MOUSE({phase}): {widget.__class__.__name__} name='{widget.objectName() or ''}'", ttl=1.0)
                except Exception as exc:
                    _diag_exc(exc, "wiretap.notify")
                return original_notify(receiver, event)

            app.notify = notify  # type: ignore[assignment]
            app._wiretap_notify_wrapped = True  # type: ignore[attr-defined]
            _log_line("Wiretap: notify hook installed")
        except Exception as exc:
            _diag_exc(exc, "wiretap.notify_install")

    def _install_focus_hook(self) -> None:
        try:
            app = QtWidgets.QApplication.instance()
            if app is None or getattr(app, "_wiretap_focus_hooked", False):
                return

            def on_focus_changed(_old, new):
                if isinstance(new, QtWidgets.QWidget) and new is not self.overlay:
                    self._emit(f"FOCUS: {new.__class__.__name__} name='{new.objectName() or ''}'", ttl=1.0)

            app.focusChanged.connect(on_focus_changed)  # type: ignore[arg-type]
            app._wiretap_focus_hooked = True  # type: ignore[attr-defined]
            _log_line("Wiretap: focus hook installed")
        except Exception as exc:
            _diag_exc(exc, "wiretap.focus_install")

    def _describe_widget(self, widget: QtWidgets.QWidget) -> str:
        msg = f"{widget.__class__.__name__} name='{widget.objectName() or ''}'"
        text = _w_text(widget)
        if text:
            msg += f" text='{text[:80]}'"
        return msg

    def _tap_signals(self) -> None:
        if self._signal_tap_installed:
            return
        self._signal_tap_installed = True

        def safe_connect(obj, attr: str, label: str) -> None:
            try:
                signal = getattr(obj, attr, None)
                if signal is None:
                    return
                key = f"_wiretap_{label}_{id(obj)}"
                if hasattr(obj, key):
                    return
                setattr(obj, key, True)
                signal.connect(lambda *args, _o=obj, _l=label: self._emit(f"SIGNAL({_l}): " + self._describe_widget(_o), ttl=1.5))
            except Exception:
                return

        for widget in self.main_window.findChildren(QtWidgets.QWidget):
            for attr in ("clicked", "toggled", "pressed", "released", "stateChanged", "currentIndexChanged", "valueChanged", "editingFinished", "textChanged"):
                safe_connect(widget, attr, attr)

        for action in self.main_window.findChildren(QtGui.QAction):
            safe_connect(action, "triggered", "triggered")

        _log_line("Wiretap: signal tap installed")

    def _start_signal_tap_watchdog(self) -> None:
        if self._tap_watchdog is not None:
            return
        self._tap_watchdog = QtCore.QTimer(self)
        self._tap_watchdog.setInterval(500)
        self._tap_watchdog.timeout.connect(self._tap_signals)
        self._tap_watchdog.start()
        _log_line("Wiretap: tap watchdog running")

    def install_signal_probes(self) -> None:
        self._ensure_global_filters()

    def _receivers(self, obj: QtCore.QObject, sig_name: str) -> Optional[int]:
        sig = getattr(obj, sig_name, None)
        if sig is None:
            return None
        signature = getattr(sig, "signal", None)
        if signature is None:
            return None
        try:
            return int(obj.receivers(signature))
        except Exception:
            return None

    def _report_signal(self, obj: QtCore.QObject, signal_name: str) -> None:
        receivers = self._receivers(obj, signal_name)
        receiver_msg = "unknown" if receivers is None else str(receivers)
        self._emit(f"{signal_name}: {self._describe_widget(obj)} receivers={receiver_msg}", ttl=1.5)  # type: ignore[arg-type]

    def _report_click(self, widget: QtWidgets.QWidget) -> None:
        self._emit(f"CLICK: {self._describe_widget(widget)} path={_obj_path(widget)}", ttl=1.5)
