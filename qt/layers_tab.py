from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtWidgets  # type: ignore

from qt.layers_panel import LayersPanel

class LayersTab(QtWidgets.QWidget):
    """Layers tab (robust minimal implementation)."""

    def __init__(self, app_core, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Layers are the behavior stack. Each layer runs one behavior and sends its pixels into the final composition. Layers can target zones, masks, or groups.")
        intro.setWordWrap(True)
        root.addWidget(intro)
        header = QtWidgets.QLabel("Build the compositing stack that behaviors will run on.")
        header.setWordWrap(True)
        root.addWidget(header)
        quick = QtWidgets.QLabel("Quick Tip: Layers stack behaviors together to build the final visual output.")
        quick.setWordWrap(True)
        root.addWidget(quick)
        stack = QtWidgets.QLabel("Layer Stack: Layers combine from top to bottom to form the final frame before operators are applied.")
        stack.setWordWrap(True)
        root.addWidget(stack)
        controls = QtWidgets.QLabel("Layer Controls: Add / Duplicate / Solo / Move layers to shape the composition stack.")
        controls.setWordWrap(True)
        root.addWidget(controls)
        shortcuts = QtWidgets.QLabel("Workflow Shortcuts: Add Layer, Duplicate, Solo, Move Up / Down, then assign Targeting and Behaviors.")
        shortcuts.setWordWrap(True)
        root.addWidget(shortcuts)
        next_step = QtWidgets.QLabel("Next: go to Behaviors to choose what each layer does.")
        next_step.setWordWrap(True)
        root.addWidget(next_step)
        prev_step = QtWidgets.QLabel("Targets define the zones, masks, and groups that layers can use.")
        prev_step.setWordWrap(True)
        root.addWidget(prev_step)

        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(LayersPanel(app_core))
