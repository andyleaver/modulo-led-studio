from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtWidgets  # type: ignore
from qt.targets_tab_state import TargetsTabStateMixin
from qt.targets_tab_actions import TargetsTabActionsMixin
from qt.targets_tab_ui import TargetsTabUiMixin


class TargetsTab(TargetsTabStateMixin, TargetsTabActionsMixin, TargetsTabUiMixin, QtWidgets.QWidget):
    """Targeting tab.

    Workflow-first surface for:
    - global preview target mask
    - project masks
    - project zones
    - project groups
    """

    def __init__(self, app_core, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self._build_ui()
