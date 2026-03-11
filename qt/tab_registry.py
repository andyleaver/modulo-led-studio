from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass

try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.scroll_wrap import wrap_scroll

# Panels / tabs
from qt.era_panel import EraPanel
from qt.layout_panel import LayoutPanel
from qt.layers_tab import LayersTab
from qt.operators_tab import OperatorsTab
from qt.rules_tab import RulesTab
from qt.signals_tab import SignalsTab
from qt.targets_tab import TargetsTab
from qt.variables_tab import VariablesTab
from qt.export_tab import ExportTab
from qt.effects_tab import EffectsTab
from qt.presets_tab import PresetsTab
from qt.playlist_tab import PlaylistTab


def _set_tab_visible_safe(tabs, index: int, visible: bool):
    try:
        if hasattr(tabs, "setTabVisible"):
            tabs.setTabVisible(index, bool(visible))
            return
    except Exception as e:
        _diag_exc(e, "qt/tab_registry.py")
    try:
        widget = tabs.widget(index)
        if widget is not None:
            widget.setVisible(bool(visible))
    except Exception as e:
        _diag_exc(e, "qt/tab_registry.py")


def apply_era_tab_gating(owner):
    """Hide/show primary studio tabs from the current era studio tool set."""
    try:
        tabs = getattr(owner, "tabs", None)
        specs = list(getattr(owner, "_era_tab_specs", []) or [])
        app_core = getattr(owner, "app_core", None)
        if tabs is None or not specs or app_core is None:
            return

        gates = {}
        try:
            fn = getattr(app_core, "get_era_gates", None)
            gates = fn() if callable(fn) else {}
        except Exception as e:
            _diag_exc(e, "qt/tab_registry.py")
            gates = {}

        allowed = set((gates or {}).get("studio_tools") or [])
        if not allowed:
            for spec in specs:
                tools = list(spec.get("tools") or [])
                if tools:
                    allowed.update(tools)

        for spec in specs:
            idx = int(spec.get("index", -1))
            tools = [str(t or "").strip() for t in (spec.get("tools") or []) if str(t or "").strip()]
            if idx < 0:
                continue
            visible = True if not tools else any(tool in allowed for tool in tools)
            _set_tab_visible_safe(tabs, idx, visible)

        try:
            cur = int(tabs.currentIndex())
            if cur >= 0 and hasattr(tabs, "isTabVisible") and not tabs.isTabVisible(cur):
                for spec in specs:
                    idx = int(spec.get("index", -1))
                    if idx >= 0 and (not hasattr(tabs, "isTabVisible") or tabs.isTabVisible(idx)):
                        tabs.setCurrentIndex(idx)
                        break
        except Exception:
            pass
    except Exception as e:
        _diag_exc(e, "qt/tab_registry.py")


def _make_intro_card(title: str, body: str):
    card = QtWidgets.QFrame()
    try:
        card.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        card.setObjectName("WorkflowIntroCard")
        card.setStyleSheet("#WorkflowIntroCard { border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }")
    except Exception:
        pass
    lay = QtWidgets.QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(4)

    head = QtWidgets.QLabel(title)
    try:
        head.setStyleSheet("font-size: 16px; font-weight: 700;")
    except Exception:
        pass
    body_lbl = QtWidgets.QLabel(body)
    try:
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet("color: #b8bcc6;")
    except Exception:
        pass
    lay.addWidget(head)
    lay.addWidget(body_lbl)
    return card


def _make_side_guide(title: str, sections):
    frame = QtWidgets.QFrame()
    try:
        frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        frame.setObjectName("WorkflowGuideRail")
        frame.setStyleSheet("#WorkflowGuideRail { border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }")
    except Exception:
        pass
    frame.setMinimumWidth(210)
    frame.setMaximumWidth(260)
    lay = QtWidgets.QVBoxLayout(frame)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)

    hdr = QtWidgets.QLabel("How to use this tab")
    try:
        hdr.setStyleSheet("font-weight: 700;")
    except Exception:
        pass
    lay.addWidget(hdr)

    caption = QtWidgets.QLabel(f"Work top to bottom in {title}. Every major capability is selectable here without typing internal names.")
    try:
        caption.setWordWrap(True)
        caption.setStyleSheet("color: #9aa3ad;")
    except Exception:
        pass
    lay.addWidget(caption)

    for idx, section in enumerate([s for s in sections if s], start=1):
        sec_title = section[0]
        item = QtWidgets.QLabel(f"{idx}. {sec_title}")
        try:
            item.setWordWrap(True)
            item.setStyleSheet("padding: 4px 0;")
        except Exception:
            pass
        lay.addWidget(item)
    lay.addStretch(1)
    return frame


def _make_composite_tab(title: str, subtitle: str, sections):
    w = QtWidgets.QWidget()
    v = QtWidgets.QVBoxLayout(w)
    v.setContentsMargins(10, 10, 10, 10)
    v.setSpacing(10)
    v.addWidget(_make_intro_card(title, subtitle), 0)

    body = QtWidgets.QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(10)
    guide = _make_side_guide(title, sections)
    body.addWidget(guide, 0)

    toolbox = QtWidgets.QToolBox()
    try:
        toolbox.setObjectName("WorkflowToolbox")
        toolbox.setStyleSheet("QToolBox::tab { padding: 8px 10px; font-weight: 600; }")
    except Exception:
        pass
    for section in sections:
        if not section:
            continue
        sec_title, sec_subtitle, sec_widget = section
        page = QtWidgets.QWidget()
        pv = QtWidgets.QVBoxLayout(page)
        pv.setContentsMargins(6, 8, 6, 8)
        pv.setSpacing(8)
        if sec_subtitle:
            lbl = QtWidgets.QLabel(sec_subtitle)
            try:
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: #9aa3ad;")
            except Exception:
                pass
            pv.addWidget(lbl)
        pv.addWidget(sec_widget, 1)
        toolbox.addItem(page, sec_title)
    if toolbox.count() > 0:
        toolbox.setCurrentIndex(0)
    body.addWidget(toolbox, 1)
    v.addLayout(body, 1)
    return w


def _apply_workflow_tooltips(owner):
    try:
        tips = {
            "1. Surface": "Set the physical LED surface, layout, mapping, and any target helpers.",
            "2. Layers": "Build the visual stack and choose how layers behave.",
            "3. Behaviour": "Connect triggers, variables, rules, presets, and reusable behaviour.",
            "4. Inputs": "Use audio, time, and signal routing without needing internal names.",
            "5. Preview": "See live output, sequencing, and playback context while you build.",
            "6. Export": "Choose the target hardware and build firmware for deployment.",
        }
        for i in range(owner.tabs.count()):
            label = owner.tabs.tabText(i)
            if label in tips:
                owner.tabs.setTabToolTip(i, tips[label])
    except Exception:
        pass


def build_tabs(owner, outer_layout: QtWidgets.QLayout, app_core):
    """Create and attach the main QTabWidget and workflow-first tab structure."""
    owner.tabs = QtWidgets.QTabWidget()

    try:
        def update_workflow_step(idx):
            try:
                label = owner.tabs.tabText(idx)
                if hasattr(owner, "_workflow_step"):
                    owner._workflow_step.setText(f"Current Step: {label}")
            except Exception:
                pass
        owner.tabs.currentChanged.connect(update_workflow_step)
    except Exception:
        pass

    try:
        owner.tabs.setDocumentMode(True)
        owner.tabs.setElideMode(QtCore.Qt.TextElideMode.ElideRight)
    except Exception:
        pass

    try:
        owner.tabs.setMovable(False)
    except Exception as e:
        _diag_exc(e, "qt/tab_registry.py")

    on_layout_changed = getattr(owner, "_on_layout_changed", None)

    owner.app_core = app_core
    owner.era_panel = EraPanel(app_core, parent=owner)
    owner.layout_panel = LayoutPanel(app_core, controller=owner, on_layout_changed_cb=on_layout_changed)
    owner.targets_tab = TargetsTab(app_core, controller=owner)
    owner.layers_tab = LayersTab(app_core, controller=owner)
    owner.effects_tab = EffectsTab(app_core, controller=owner)
    owner.signals_tab = SignalsTab(app_core, controller=owner)
    owner.variables_tab = VariablesTab(app_core, controller=owner)
    owner.rules_tab = RulesTab(app_core, controller=owner)
    owner.operators_tab = OperatorsTab(app_core, controller=owner)
    owner.presets_tab = PresetsTab(app_core, controller=owner)
    owner.playlist_tab = PlaylistTab(app_core, controller=owner)
    owner.export_tab = ExportTab(app_core, controller=owner)

    owner._era_tab_specs = []

    def _add_tab(widget, label: str, tools):
        idx = owner.tabs.addTab(widget, label)
        owner._era_tab_specs.append({"index": idx, "label": label, "tools": list(tools or [])})

    owner.surface_workflow_tab = _make_composite_tab(
        "Surface",
        "Start here. Choose the LED surface and mapping with dropdowns, toggles, and helpers so users never need to know internal names first.",
        [
            ("Surface Setup", "Define whether you are building for a strip or cells / matrix style surface.", owner.layout_panel),
            ("Targets & Helpers", "Optional grouping, zones, and target helpers stay here so hardware setup lives in one place.", owner.targets_tab),
        ],
    )

    owner.layers_workflow_tab = _make_composite_tab(
        "Layers",
        "Build the visual stack here. Add layers, choose behaviours/effects, and shape the final output without leaving the layer workflow.",
        [
            ("Layer Stack", "Create, reorder, solo, and inspect layers from a single main stack.", owner.layers_tab),
            ("Behaviour & Effects", "Choose what each layer does without forcing users to know engine names first.", owner.effects_tab),
            ("Operator Overrides", "Advanced shaping stays available, but inside the layer workflow instead of as a separate top-level tab.", owner.operators_tab),
        ],
    )

    owner.behaviour_workflow_tab = _make_composite_tab(
        "Behaviour",
        "Turn visuals into systems. Build behaviour with rules, variables, and presets using discoverable controls instead of hidden names.",
        [
            ("Rules", "Set up triggers and actions in one place.", owner.rules_tab),
            ("Variables", "Shared state for behaviour lives here so rule logic stays readable.", owner.variables_tab),
            ("Presets", "Save reusable behaviour states and scene setups.", owner.presets_tab),
        ],
    )

    owner.inputs_workflow_tab = _make_composite_tab(
        "Inputs",
        "Drive behaviour from audio, time, and routed signals. Audio remains first-class with simulator and live input paths, including seven bands per channel.",
        [
            ("Signals & Routing", "Select inputs and routes from structured controls instead of typing canonical signal names.", owner.signals_tab),
        ],
    )

    owner.preview_workflow_tab = _make_composite_tab(
        "Preview",
        "The strip stays across the top and the matrix stays on the right. Use this tab for playback context, sequencing, and quick preview-oriented controls.",
        [
            ("Timeline & Playlist", "Sequence presets and preview playback flow here while the live previews remain visible in the main shell.", owner.playlist_tab),
        ],
    )

    owner.export_workflow_tab = _make_composite_tab(
        "Export",
        "Finish here. Choose the hardware target and deployment options once the project looks right in preview.",
        [
            ("Build & Deploy", "Export for real hardware targets without mixing deployment controls into the creation tabs.", owner.export_tab),
        ],
    )

    _add_tab(owner.surface_workflow_tab, "Surface", ["surface_layout", "target_setup", "matrix_tools", "pixel_controls"])
    _add_tab(owner.layers_workflow_tab, "Layers", ["layer_stack", "effect_library", "operators_panel"])
    _add_tab(owner.behaviour_workflow_tab, "Behaviour", ["rules_editor", "variables_panel", "preset_browser", "modulotors"])
    _add_tab(owner.inputs_workflow_tab, "Inputs", ["signal_routing", "audio_signals"])
    _add_tab(owner.preview_workflow_tab, "Preview", ["playlist", "effect_library", "layer_stack"])
    _add_tab(owner.export_workflow_tab, "Export", ["export_panel"])

    outer_layout.addWidget(owner.tabs, 1)
    _apply_workflow_tooltips(owner)
    apply_era_tab_gating(owner)

    try:
        owner.tabs.setCurrentIndex(0)
    except Exception:
        pass
