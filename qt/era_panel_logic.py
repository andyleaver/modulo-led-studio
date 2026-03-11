from __future__ import annotations

"""Composed era-panel logic mixins.

Keeps the public import stable while separating:
- progression / navigation state
- workbench behaviour / verification
- explanatory text generation
"""

from qt.era_panel_progress import EraPanelProgressMixin
from qt.era_panel_workbench import EraPanelWorkbenchMixin
from qt.era_panel_text import EraPanelTextMixin


class EraPanelLogicMixin(
    EraPanelProgressMixin,
    EraPanelWorkbenchMixin,
    EraPanelTextMixin,
):
    pass
