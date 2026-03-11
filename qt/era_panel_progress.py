from __future__ import annotations

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
from typing import Dict, Any, Tuple
import time

from qt.qt_compat import QtCore, QtGui, QtWidgets, Signal

Qt = QtCore.Qt
QTimer = QtCore.QTimer
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QFrame = QtWidgets.QFrame
QTextEdit = QtWidgets.QTextEdit
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QSizePolicy = QtWidgets.QSizePolicy
QSlider = QtWidgets.QSlider
QSpinBox = QtWidgets.QSpinBox
QPainter = QtGui.QPainter
QColor = QtGui.QColor
QPen = QtGui.QPen

from app.eras.era_history import get_era, get_eras, get_phase_note, get_workbench_for_era
from app.project_canonical import apply_project_root
from app.eras.era_progression import get_active_era, get_unlocked, unlock_next, set_active, gates_for_project

class EraPanelProgressMixin:
    def _project_dict(self) -> Dict[str, Any]:
            try:
                p = getattr(self.app_core, "project", None)
                if isinstance(p, dict):
                    return p
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")
            return {}

    def _persist_project(self, project: Dict[str, Any]):
            try:
                setattr(self.app_core, "project", project)
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")
            try:
                fn = getattr(self.app_core, "notify_project_changed", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
            try:
                fn = getattr(self.app_core, "mark_dirty", None)
                if callable(fn):
                    fn()
            except Exception:
                pass

    def _progress_active_era_id(self) -> str:
            try:
                return str(get_active_era(self._project_dict()) or get_eras()[0].era_id)
            except Exception:
                return get_eras()[0].era_id

    def _progress_unlocked_ids(self) -> list[str]:
            try:
                return [str(x) for x in get_unlocked(self._project_dict())]
            except Exception:
                return [get_eras()[0].era_id]

    def _progress_set_active_era(self, era_id: str):
            try:
                p = dict(self._project_dict() or {})
                set_active(p, str(era_id or ""))
                self._persist_project(p)
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")

    def _progress_unlock_next(self) -> str | None:
            try:
                p = dict(self._project_dict() or {})
                nxt = unlock_next(p)
                self._persist_project(p)
                return nxt
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")
                return None

    def _progress_mark_verified(self, era_id: str, ok: bool = True):
            try:
                p = dict(self._project_dict() or {})
                st = dict(p.get("era_state") or {})
                done = dict(st.get("done_map") or {})
                done[str(era_id)] = bool(ok)
                st["done_map"] = done
                p, _validation, _changes = apply_project_root(p, "era_state", st)
                self._persist_project(p)
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")

    def _progress_done_map(self) -> Dict[str, bool]:
            try:
                p = self._project_dict()
                st = dict(p.get("era_state") or {})
                raw = dict(st.get("done_map") or {})
                return {str(k): bool(v) for k, v in raw.items()}
            except Exception:
                return {}

    def _project_era_gates(self) -> Dict[str, Any]:
            try:
                return dict(gates_for_project(self._project_dict()) or {})
            except Exception:
                return {}

    def _reset_workbench_for_era(self, era_id: str):
            """Ensure the workbench starts in the canonical historical state."""
            try:
                seed = self._seed_state_for(str(era_id))
                self._wb_state = dict(seed or {})
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")

    def _active_era_id(self) -> str:
            return self._progress_active_era_id()

    def _display_id(self) -> str:
            return self._display_era_id or self._active_era_id()



    def _browsable_era_ids(self) -> list[str]:
            """Return era ids that can be browsed in the current progression state."""
            try:
                eras = [str(getattr(e, "era_id", "") or "") for e in get_eras()]
                active = str(self._active_era_id() or "")
                unlocked = [str(x) for x in (self._progress_unlocked_ids() or []) if str(x)]
                known = [str(x) for x in (getattr(self, "_known_unlocked", []) or []) if str(x)]
                allowed = []
                seen = set()
                for era_id in eras:
                    if not era_id or era_id in seen:
                        continue
                    if era_id == active or era_id in unlocked or era_id in known:
                        allowed.append(era_id)
                        seen.add(era_id)
                if active and active not in seen:
                    allowed.append(active)
                return allowed or eras[:1]
            except Exception:
                try:
                    return [str(get_eras()[0].era_id)]
                except Exception:
                    return []

    def _can_browse_to(self, era_id: str) -> bool:
            try:
                era_id = str(era_id or "")
                if not era_id:
                    return False
                return era_id in set(self._browsable_era_ids() or [])
            except Exception:
                return False

    def _populate_browse(self):
            self.browse_combo.blockSignals(True)
            self.browse_combo.clear()
            unlocked = set(self._progress_unlocked_ids() or [])
            self._known_unlocked = list(unlocked)
            browsable = set(self._browsable_era_ids() or [])
            for e in get_eras():
                if browsable and e.era_id not in browsable:
                    continue
                self.browse_combo.addItem(e.title, e.era_id)
            self.browse_combo.blockSignals(False)

    def _on_browse_changed(self, idx: int):
            try:
                era_id = self.browse_combo.itemData(idx)
                if isinstance(era_id, str) and era_id and self._can_browse_to(era_id):
                    self._display_era_id = era_id
                else:
                    self._display_era_id = None
            except Exception:
                self._display_era_id = None
            self.refresh()

    def _set_display_id(self, era_id: str):
            try:
                self._display_era_id = str(era_id or "") or None
            except Exception:
                self._display_era_id = None
            self.refresh()

    def _jump_to_active(self):
            self._display_era_id = None
            self.refresh()

    def _open_workspace(self):
            try:
                owner = self._owner_window()
                if owner is None:
                    return
                try:
                    # At the effect-picker plateau, force the allowed normal-app tabs visible
                    # before choosing the target tab. This avoids getting stuck on the Era page
                    # if the normal refresh path has not yet exposed them.
                    gates = {}
                    try:
                        fn = getattr(self.app_core, "get_era_gates", None)
                        gates = fn() if callable(fn) else self._project_era_gates()
                    except Exception:
                        gates = {}
                    model = str((gates or {}).get("control_model") or "").strip().lower()
                    if model == "effect_picker":
                        try:
                            from qt.tab_registry import _set_tab_visible_safe
                            allowed = set((gates or {}).get("studio_tools") or [])
                            for spec in list(getattr(owner, "_era_tab_specs", []) or []):
                                idx = int(spec.get("index", -1))
                                tool = str(spec.get("tool") or "").strip()
                                if idx >= 0 and tool:
                                    _set_tab_visible_safe(owner.tabs, idx, tool in allowed)
                        except Exception as e:
                            _diag_exc(e, "qt/era_panel.py")
                    if hasattr(owner, "refresh_era_ui"):
                        owner.refresh_era_ui(focus_modulo=False)
                    # And then force-switch to the preferred effect-picker workspace tab.
                    try:
                        if hasattr(owner, "_preferred_studio_tab_index") and hasattr(owner, "tabs"):
                            target_idx = owner._preferred_studio_tab_index(gates=gates, focus_modulo=False)
                            owner.tabs.setCurrentIndex(int(target_idx))
                    except Exception as e:
                        _diag_exc(e, "qt/era_panel.py")
                except Exception as e:
                    _diag_exc(e, "qt/era_panel.py")
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")

    def _on_unlock_modulo(self):
            """Explicitly continue from the effect-picker plateau into Modulo."""
            try:
                # Ensure Modulo era is unlocked and active in project progression state.
                unlocked = set(self._progress_unlocked_ids())
                if "era_now" not in unlocked:
                    while True:
                        nxt = self._progress_unlock_next()
                        if not nxt or nxt == "era_now":
                            break
                self._progress_set_active_era("era_now")
                self._progress_mark_verified("era_usage_plateau", True)
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")
            self._display_era_id = None
            try:
                self.refresh()
            except Exception as e:
                _diag_exc(e, "qt/era_panel.py")
            self._refresh_owner_ui(focus_modulo=True)

