try:
    from qt.qt_compat import QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtWidgets  # type: ignore

from qt.rules_tab_ui import RulesTabUiMixin
from qt.rules_tab_state import RulesTabStateMixin
from qt.rules_tab_actions import RulesTabActionsMixin


class RulesTab(QtWidgets.QWidget, RulesTabUiMixin, RulesTabStateMixin, RulesTabActionsMixin):
    """Rules tab container."""

    def __init__(self, app_core, controller=None):
        super().__init__()
        self.app_core = app_core
        self.controller = controller
        self._all_addresses_cache = []
        self._build_ui()
