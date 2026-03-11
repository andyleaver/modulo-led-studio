from __future__ import annotations

from pathlib import Path
from qt.era_onboarding import EraOnboardingWindow
from qt.qt_compat import QtCore, QtWidgets  # type: ignore


def user_flag_path(app_core, filename: str) -> Path | None:
    try:
        run_root = getattr(app_core, 'run_root', None)
        if run_root is None:
            run_root = Path(__file__).resolve().parents[1]
        path = Path(str(run_root)) / 'user_data' / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return None


class MainWindowEraMixin:
    def _era_progress_path(self):
        return user_flag_path(self.app_core, 'era_progress.txt')

    def _era_completed(self) -> bool:
        try:
            fn = getattr(self.app_core, 'is_era_complete', None)
            if callable(fn):
                return bool(fn())
        except Exception:
            pass
        try:
            path = self._era_progress_path()
            if path and path.exists():
                return path.read_text(encoding='utf-8', errors='ignore').strip() == 'done'
        except Exception:
            pass
        return False

    def _mark_era_completed(self):
        try:
            fn = getattr(self.app_core, 'set_era_complete', None)
            if callable(fn):
                fn(True)
        except Exception:
            pass
        try:
            path = self._era_progress_path()
            if path:
                path.write_text('done\n', encoding='utf-8')
        except Exception:
            pass

    def _diag_console_fail_banner(self, msg: str) -> None:
        try:
            label = QtWidgets.QLabel(msg)
            label.setStyleSheet('background:#8b0000;color:white;padding:6px;font-weight:bold;')
            label.setWordWrap(True)
            central = self.centralWidget()
            if central is None:
                return
            layout = central.layout()
            if layout is not None:
                layout.insertWidget(0, label)
        except Exception:
            pass

    def _era_stop_here_available(self) -> bool:
        try:
            fn = getattr(self.app_core, 'get_era_gates', None)
            gates = fn() if callable(fn) else {}
            return bool((gates or {}).get('stop_here_ok', False))
        except Exception:
            return False

    def _set_studio_locked_for_era(self, locked: bool):
        try:
            tabs = getattr(self, 'tabs', None)
            if tabs is not None:
                tabs.setEnabled(not bool(locked))
        except Exception:
            pass
        if locked:
            try:
                if hasattr(self, '_workflow_banner'):
                    self._workflow_banner.setText(
                        'Historical Era Journey Active: complete the current era journey to unlock studio interaction.'
                    )
            except Exception:
                pass
            try:
                if hasattr(self, '_workflow_mode'):
                    self._workflow_mode.setText('Mode: Era Journey')
            except Exception:
                pass

    def _restore_workflow_status_after_era_lock(self):
        try:
            mode_lower = str(self._load_studio_mode() or 'full_modulo').strip().lower()
        except Exception:
            mode_lower = 'full_modulo'

        stop_here_ok = self._era_stop_here_available()
        try:
            if hasattr(self, '_workflow_banner'):
                if stop_here_ok and mode_lower != 'full_modulo':
                    self._workflow_banner.setText(
                        'Effect Picker Plateau: stay here with the familiar LED-app model, or reopen the Era journey later to continue toward Modulo.'
                    )
                elif mode_lower == 'effect_picker':
                    self._workflow_banner.setText(
                        'Workflow: Surface → Layers → Preview → Export'
                    )
                else:
                    self._workflow_banner.setText(
                        'Workflow: Surface → Layers → Behaviour → Inputs → Preview → Export'
                    )
        except Exception:
            pass
        try:
            if hasattr(self, '_workflow_mode'):
                if stop_here_ok and mode_lower != 'full_modulo':
                    self._workflow_mode.setText('Mode: Effect Picker Plateau')
                else:
                    self._workflow_mode.setText('Mode: Effect Picker' if mode_lower == 'effect_picker' else 'Mode: Full Modulo')
        except Exception:
            pass

    def _maybe_launch_era_onboarding(self):
        try:
            completed = self._era_completed()
            stop_here_ok = self._era_stop_here_available()
            if completed:
                self._set_studio_locked_for_era(False)
                self._restore_workflow_status_after_era_lock()
                return
            if not stop_here_ok:
                self._set_studio_locked_for_era(True)
                self._open_era_onboarding()
                return
            self._set_studio_locked_for_era(False)
            try:
                self._apply_studio_mode('effect_picker')
            except Exception:
                pass
            try:
                if hasattr(self, '_workflow_mode'):
                    self._workflow_mode.setText('Mode: Effect Picker Plateau')
            except Exception:
                pass
            try:
                if hasattr(self, '_workflow_banner'):
                    self._workflow_banner.setText(
                        'Effect Picker Plateau: stay here with the familiar LED-app model, or reopen the Era journey later to continue toward Modulo.'
                    )
            except Exception:
                pass
        except Exception:
            pass

    def _reopen_era_journey(self):
        try:
            self._open_era_onboarding()
        except Exception:
            pass

    def _open_era_onboarding(self):
        try:
            if getattr(self, '_era_window', None) is None:
                self._era_window = EraOnboardingWindow(self.app_core, parent=self)
                try:
                    self._era_window.completed.connect(self._on_era_onboarding_completed)
                except Exception:
                    pass
            try:
                self._era_window.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            except Exception:
                pass
            self._era_window.show()
            try:
                self._era_window.raise_()
            except Exception:
                pass
            try:
                self._era_window.activateWindow()
            except Exception:
                pass
        except Exception:
            pass

    def _on_era_onboarding_completed(self):
        try:
            self._mark_era_completed()
        except Exception:
            pass
        try:
            if getattr(self, '_era_window', None) is not None:
                self._era_window.close()
        except Exception:
            pass
        try:
            self._set_studio_locked_for_era(False)
        except Exception:
            pass
        try:
            self._apply_studio_mode('full_modulo')
        except Exception:
            pass
        try:
            self._restore_workflow_status_after_era_lock()
        except Exception:
            pass
