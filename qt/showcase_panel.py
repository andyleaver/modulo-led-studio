from __future__ import annotations

try:
    from PySide6 import QtCore, QtWidgets  # type: ignore
except Exception:  # pragma: no cover
    from PyQt6 import QtCore, QtWidgets  # type: ignore

from app.showcases.registry import get_showcases

class ShowcasePanel(QtWidgets.QWidget):
    """Small, additive panel that loads and explains a showcase project."""

    def __init__(self, app_core, on_layout_changed_cb):
        super().__init__()
        self.app_core = app_core
        self._on_layout_changed_cb = on_layout_changed_cb

        self._showcases = get_showcases()
        self._step_idx = 0

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Picker row
        row = QtWidgets.QHBoxLayout()
        self.combo = QtWidgets.QComboBox()
        for sc in self._showcases:
            self.combo.addItem(sc.title, sc.id)
        row.addWidget(self.combo, 1)

        self.btn_load = QtWidgets.QPushButton("Load")
        self.btn_load.clicked.connect(self._load_selected)
        row.addWidget(self.btn_load)

        outer.addLayout(row)

        self.subtitle = QtWidgets.QLabel("")
        self.subtitle.setWordWrap(True)
        outer.addWidget(self.subtitle)

        # Guide box
        self.lbl_step = QtWidgets.QLabel("")
        self.lbl_step.setWordWrap(True)
        outer.addWidget(self.lbl_step, 1)

        nav = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("Prev")
        self.btn_prev.clicked.connect(self._prev)
        nav.addWidget(self.btn_prev)

        self.btn_next = QtWidgets.QPushButton("Next")
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_next)

        self.btn_exit = QtWidgets.QPushButton("Exit Guide")
        self.btn_exit.clicked.connect(self._exit)
        nav.addWidget(self.btn_exit)

        outer.addLayout(nav)
        outer.addStretch(0)

        self._sync_subtitle()
        self._render_step()

    def _sync_subtitle(self):
        sc = self._current_showcase()
        self.subtitle.setText(sc.subtitle if sc else "")

    def _current_showcase(self):
        sid = self.combo.currentData()
        for sc in self._showcases:
            if sc.id == sid:
                return sc
        return self._showcases[0] if self._showcases else None

    def _load_selected(self):
        sc = self._current_showcase()
        if not sc:
            return
        proj = sc.builder()
        # Step 3: Showcase export guardrails (truth from export eligibility)
        try:
            from export.export_eligibility import get_eligibility, ExportStatus
            layers = (proj or {}).get("layers", []) or []
            blocked = []
            preview = []
            for li, layer in enumerate(layers):
                beh = layer.get("behavior") or layer.get("behavior_key") or layer.get("effect") or ""
                if isinstance(beh, dict):
                    beh = beh.get("key") or beh.get("id") or ""
                beh = str(beh) if beh is not None else ""
                if not beh:
                    continue
                elig = get_eligibility(beh)
                if elig.status == ExportStatus.BLOCKED:
                    blocked.append((li, beh, elig.reason))
                elif elig.status == ExportStatus.PREVIEW_ONLY:
                    preview.append((li, beh, elig.reason))
            ui = dict((proj or {}).get("ui") or {})
            ui["showcase_id"] = getattr(sc, "id", "") or ""
            ui["showcase_title"] = getattr(sc, "title", "") or ""
            ui["showcase_export_blocked"] = bool(blocked)
            ui["showcase_export_preview_only_count"] = int(len(preview))
            if blocked:
                ui["showcase_export_blocked_reasons"] = [
                    f"Layer {i+1}: {k} — {r}" for (i, k, r) in blocked
                ]
            else:
                ui["showcase_export_blocked_reasons"] = []
            (proj or {})["ui"] = ui
        except Exception:
            pass
        # Replace current project
        # Load showcase project into the live app
        try:
            self.app_core.project = proj
        except Exception:
            try:
                self.app_core.pm.load_project_dict(proj)
            except Exception:
                pass
        # Rebuild preview engine + geometry
        try:
            self.app_core._rebuild_full_preview_engine()
        except Exception:
            pass
        # Refresh layout-dependent UI (strip header vs matrix)
        try:
            self._on_layout_changed_cb()
        except Exception:
            pass
        # Reset guide steps
        self._step_idx = 0
        self._render_step()

    def _exit(self):
        self._step_idx = 0
        self._render_step()

    def _prev(self):
        self._step_idx = max(0, self._step_idx - 1)
        self._render_step()

    def _next(self):
        self._step_idx = min(self._max_steps() - 1, self._step_idx + 1)
        self._render_step()

    def _max_steps(self) -> int:
        sc = self._current_showcase()
        return len(sc.steps) if (sc and getattr(sc, 'steps', None)) else 1

    def _render_step(self):
        sc = self._current_showcase()
        if not sc:
            self.lbl_step.setText("No showcases available.")
            return
        self._sync_subtitle()

        steps = list(getattr(sc, 'steps', []) or [])
        if not steps:
            steps = ["No guide steps defined for this showcase yet."]
        i = min(self._step_idx, len(steps)-1)
        self.lbl_step.setText(f"Step {i+1}/{len(steps)}\n\n{steps[i]}")
        self.btn_prev.setEnabled(i > 0)
        self.btn_next.setEnabled(i < len(steps) - 1)
