from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtWidgets  # type: ignore
from qt.operators_tab_state import OperatorsTabStateMixin
from qt.operators_tab_actions import OperatorsTabActionsMixin
from qt.operators_tab_ui import OperatorsTabUiMixin


class OperatorsTab(OperatorsTabStateMixin, OperatorsTabActionsMixin, OperatorsTabUiMixin, QtWidgets.QWidget):
    """Operators tab.

    Full post-fx operator UI will come later; for now this gives an editable,
    reliable view of project.postfx so all doors are reachable.
    """

    def __init__(self, app_core, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self._build_ui()
