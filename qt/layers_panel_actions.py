from __future__ import annotations

"""Composed layers panel action mixins.

Keeps the public import stable while splitting responsibilities into:
- core selection / refresh
- parameter editors and bindings
- targeting / address browser
- kernel / layer actions
"""

from qt.layers_panel_core import LayersPanelCoreMixin
from qt.layers_panel_params import LayersPanelParamsMixin
from qt.layers_panel_targeting import LayersPanelTargetingMixin
from qt.layers_panel_kernel import LayersPanelKernelMixin


class LayersPanelActionsMixin(
    LayersPanelCoreMixin,
    LayersPanelParamsMixin,
    LayersPanelTargetingMixin,
    LayersPanelKernelMixin,
):
    pass
