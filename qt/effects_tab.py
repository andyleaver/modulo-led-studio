from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtWidgets  # type: ignore
from qt.effects_tab_catalog import EffectsTabCatalogMixin
from qt.effects_tab_actions import EffectsTabActionsMixin
from qt.effects_tab_ui import EffectsTabUiMixin


class EffectsTab(EffectsTabCatalogMixin, EffectsTabActionsMixin, EffectsTabUiMixin, QtWidgets.QWidget):
    """Effects browser (normal LED-app workflow).

    In Full Modulo this is the Behaviors stage. Adding from here should
    create a real layer entry and trigger the same project/preview flow as
    the Layers editor.
    """

    def __init__(self, app_core, controller=None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self._build_ui()
