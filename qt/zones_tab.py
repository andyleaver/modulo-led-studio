
from __future__ import annotations
from typing import Optional, List, Dict
from app.project_canonical import apply_project_root
from qt.qt_compat import QtWidgets  # type: ignore

class ZonesTab(QtWidgets.QWidget):
    """Zones tab.

    Provides a simple UI for creating and editing logical pixel zones.
    Zones are important for Modulo because users can target subsets of LEDs
    without restricting engine capability.
    """

    def __init__(self, app_core, controller=None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller

        root = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Zones define reusable pixel groups. "
            "Effects, rules, and operators can target zones instead of the full surface."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        top = QtWidgets.QHBoxLayout()

        self.txt_name = QtWidgets.QLineEdit()
        self.txt_name.setPlaceholderText("Zone name")
        top.addWidget(self.txt_name)

        self.txt_range = QtWidgets.QLineEdit()
        self.txt_range.setPlaceholderText("Pixel range (example: 0-31)")
        top.addWidget(self.txt_range)

        self.btn_add = QtWidgets.QPushButton("Add Zone")
        self.btn_add.clicked.connect(self._add)
        top.addWidget(self.btn_add)

        root.addLayout(top)

        self.list = QtWidgets.QListWidget()
        root.addWidget(self.list, 1)

        btns = QtWidgets.QHBoxLayout()

        self.btn_remove = QtWidgets.QPushButton("Remove")
        self.btn_remove.clicked.connect(self._remove)
        btns.addWidget(self.btn_remove)

        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.reload)
        btns.addWidget(self.btn_refresh)

        btns.addStretch(1)
        root.addLayout(btns)

        self.reload()

    def _project(self) -> Dict:
        try:
            return dict(getattr(self.app_core, "project") or {})
        except Exception:
            return {}

    def _set_project(self, proj: Dict):
        try:
            setattr(self.app_core, "project", proj)
        except Exception:
            pass

    def reload(self):
        proj = self._project()
        zones = list(proj.get("zones") or [])

        self.list.clear()
        for z in zones:
            nm = str(z.get("name"))
            rg = str(z.get("range"))
            self.list.addItem(f"{nm}  [{rg}]")

    def _add(self):
        name = (self.txt_name.text() or "").strip()
        rng = (self.txt_range.text() or "").strip()

        if not name or not rng:
            return

        proj = self._project()
        zones: List[Dict] = list(proj.get("zones") or [])

        zones.append({
            "name": name,
            "range": rng
        })

        proj, _snap, _changes = apply_project_root(proj, "zones", zones)
        self._set_project(proj)

        self.txt_name.clear()
        self.txt_range.clear()

        self.reload()

    def _remove(self):
        idx = int(self.list.currentRow())
        if idx < 0:
            return

        proj = self._project()
        zones = list(proj.get("zones") or [])

        if idx < len(zones):
            zones.pop(idx)

        proj, _snap, _changes = apply_project_root(proj, "zones", zones)
        self._set_project(proj)
        self.reload()
