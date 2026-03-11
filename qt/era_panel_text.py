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
from app.eras.era_progression import get_active_era, get_unlocked, unlock_next, set_active, gates_for_project

class EraPanelTextMixin:
    def _context_text_for_era(self):
            try:
                era = get_era(self._display_id())
                title = getattr(era, "title", "")
                year = getattr(era, "start_year", "")
                phase = str(getattr(getattr(era, "gates", None), "phase_kind", "historical") or "historical")

                if phase == "plateau":
                    return (
                        "This is the Effect Picker Plateau. Modern LED apps typically stop here. "
                        "Users select from prebuilt effects, but deeper behavioural control is hidden."
                    )
                if phase == "modulo":
                    return (
                        "Modulo removes the artificial ceiling imposed by conventional LED apps. "
                        "Every controllable system becomes accessible: rules, signals, layers, and behaviours."
                    )

                return (
                    f"{year}: {title}. "
                    "This era represents what people could realistically do with LEDs at that time. "
                    "Capabilities are intentionally constrained to match historical practice."
                )
            except Exception:
                return ""

    def _challenge_summary_text(self) -> str:
            try:
                era = get_era(self._display_id())
                era_id = str(getattr(era, "era_id", "") or "")
                phase = str(getattr(getattr(era, "gates", None), "phase_kind", "historical") or "historical")
                verified = bool((self._progress_done_map() or {}).get(era_id, False))

                if phase == "plateau":
                    return (
                        "Challenge status: the effect-picker plateau does not require verification. "
                        "This is the stopping point where users may stay, or later continue onward to Modulo."
                    )
                if phase == "modulo":
                    return (
                        "Challenge status: Modulo is the final unlock. Historical verification is complete and the full control model is available."
                    )

                if verified:
                    return "Challenge status: verified. This era has been completed and the next era should be available."
                return "Challenge status: not yet verified. Complete the historically accurate task below to unlock the next era."
            except Exception:
                return ""

    def _challenge_steps_text(self) -> str:
            try:
                era = get_era(self._display_id())
                wb = get_workbench_for_era(era)
                if wb is None:
                    return ""
                steps = list(getattr(wb, "verify_steps", []) or [])
                if not steps:
                    return ""
                return "Challenge steps:\n" + "\n".join([f"• {s}" for s in steps])
            except Exception:
                return ""

    def _challenge_result_text(self) -> str:
            try:
                active = str(self._active_era_id() or "")
                display = str(self._display_id() or "")
                unlocked = list(self._progress_unlocked_ids() or [])
                eras = [str(getattr(e, "era_id", "") or "") for e in get_eras()]
                if display != active:
                    return "Result note: you are browsing a different era. Jump to the current era to complete its challenge."
                if active == "era_now":
                    return "Result note: full Modulo is now available."
                try:
                    idx = eras.index(active)
                except ValueError:
                    idx = -1
                nxt = eras[idx + 1] if idx >= 0 and idx + 1 < len(eras) else ""
                nxt_title = getattr(get_era(nxt), "title", nxt) if nxt else ""
                verified = bool((self._progress_done_map() or {}).get(active, False))
                if verified and nxt:
                    unlocked_note = "already unlocked" if nxt in unlocked else "will unlock"
                    return f"Result note: next era {unlocked_note}: {nxt_title}."
                if active == "era_usage_plateau":
                    return "Result note: you may stay on the plateau or explicitly unlock Modulo."
                return "Result note: verification unlocks the next historical era."
            except Exception:
                return ""

    def _plateau_summary_text(self) -> str:
            try:
                era = get_era(self._display_id())
                phase = str(getattr(getattr(era, "gates", None), "phase_kind", "historical") or "historical")
                if phase != "plateau":
                    return "Plateau choice becomes relevant only when the journey reaches the modern effect-picker stopping point."
                return (
                    "You are at the Effect Picker Plateau. "
                    "This is the familiar modern LED-app model where users choose from prebuilt effects and tweak a few settings."
                )
            except Exception:
                return ""

    def _plateau_actions_text(self) -> str:
            try:
                era = get_era(self._display_id())
                phase = str(getattr(getattr(era, "gates", None), "phase_kind", "historical") or "historical")
                if phase != "plateau":
                    return ""
                return (
                    "Choice here:\n"
                    "• Use Effect Picker Path to stay in the familiar LED-app model.\n"
                    "• Unlock Modulo when you are ready to move beyond the effect-picker ceiling."
                )
            except Exception:
                return ""

    def _capability_limits_text(self):
            try:
                era = get_era(self._display_id())
                phase = str(getattr(getattr(era, "gates", None), "phase_kind", "historical") or "historical")
                year = getattr(era, "start_year", "")
                title = getattr(era, "title", "")

                if phase == "plateau":
                    return (
                        "Capability model: effect picker. "
                        "Users select prebuilt animations and adjust a few parameters. "
                        "The internal behavioural systems are hidden."
                    )

                if phase == "modulo":
                    return (
                        "Capability model: Modulo. "
                        "All systems become accessible — layers, signals, rules, behaviours, and per‑pixel control."
                    )

                return (
                    f"{year} capability limits — {title}. "
                    "Controls are intentionally constrained so that only techniques realistically available "
                    "during that period can be used."
                )
            except Exception:
                return ""

    def _nav_prev_era(self):
            try:
                ids = list(self._browsable_era_ids() or [])
                cur = str(self._display_id())
                if cur in ids:
                    i = ids.index(cur)
                    if i > 0:
                        self._set_display_id(ids[i-1])
            except Exception:
                pass

    def _nav_next_era(self):
            try:
                ids = list(self._browsable_era_ids() or [])
                cur = str(self._display_id())
                if cur in ids:
                    i = ids.index(cur)
                    if i + 1 < len(ids):
                        self._set_display_id(ids[i+1])
            except Exception:
                pass

    def _next_unlock_text(self) -> str:
            try:
                active = str(self._active_era_id() or "")
                eras = [str(getattr(e, "era_id", "") or "") for e in get_eras()]
                if active not in eras:
                    return ""
                idx = eras.index(active)
                if active == "era_now":
                    return "Next unlock: none. Full Modulo is already available."
                if idx + 1 >= len(eras):
                    return "Next unlock: none."
                nxt = eras[idx + 1]
                nxt_title = getattr(get_era(nxt), "title", nxt)
                verified = bool((self._progress_done_map() or {}).get(active, False))
                if verified:
                    return f"Next unlock: {nxt_title} is now available."
                return f"Next unlock: verify this era to unlock {nxt_title}."
            except Exception:
                return ""

