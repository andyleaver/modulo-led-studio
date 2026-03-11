from __future__ import annotations

from .main_window_era import MainWindowEraMixin
from .main_window_modes import MainWindowModeMixin


class MainWindowLogicMixin(MainWindowEraMixin, MainWindowModeMixin):
    """Combined main-window behavior mixins.

    Keep `qt/main_window.py` focused on composition while era/studio-mode logic lives
    in dedicated helpers with one clear owner per responsibility.
    """

    pass
