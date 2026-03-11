"""Headless core bridge for Qt.

Avoids creating a Tk root window when launching Qt.
Provides the minimal API expected by qt/qt_app.py.
"""

from __future__ import annotations

import os

from app.project_manager import ProjectManager
from app.eras.era_state import (
    ensure_era_in_project,
    get_era_id as _get_era_id,
    set_era_id as _set_era_id,
    is_era_complete as _is_era_complete,
    set_era_complete as _set_era_complete,
    get_era_done_map as _get_era_done_map,
    get_unlocked_era_ids as _get_unlocked_era_ids,
    mark_era_done as _mark_era_done,
    get_next_era_id as _get_next_era_id,
)
from app.eras.era_history import get_era, get_studio_tools_for_era, get_modulo_era
from app.project_model import get_surface_snapshot, get_surface_spec
from runtime.signal_bus import SignalBus
from runtime.audio_service import AudioService
from runtime.variables import get_variables_state
from runtime.rules import evaluate_rules
from qt.core_bridge_preview import (
    prepare_preview_project as _prepare_preview_project,
    build_preview_geometry_from_snapshot as _build_preview_geometry_from_snapshot,
    reapply_runtime_only_preview_state as _reapply_runtime_only_preview_state,
)
from qt.core_bridge_startup import (
    build_startup_bundle,
    ensure_layer_uids as _ensure_layer_uids,
    sync_project_manager_startup_state as _sync_project_manager_startup_state,
)
from qt.core_bridge_era import CoreBridgeEraMixin
from qt.core_bridge_runtime_state import CoreBridgeRuntimeStateMixin
from qt.core_bridge_playlist import CoreBridgePlaylistMixin
from qt.core_bridge_signals import CoreBridgeSignalsMixin
from qt.core_bridge_preview_flow import CoreBridgePreviewFlowMixin
from qt.core_bridge_project import CoreBridgeProjectMixin
from qt.core_bridge_ui_state import CoreBridgeUiStateMixin
from qt.core_bridge_flags import ERA_ENFORCEMENT_DISABLED

class CoreBridge(CoreBridgeUiStateMixin, CoreBridgeProjectMixin, CoreBridgePreviewFlowMixin, CoreBridgeSignalsMixin, CoreBridgePlaylistMixin, CoreBridgeRuntimeStateMixin, CoreBridgeEraMixin):
    def __init__(self):
        self.pm = ProjectManager()
        self._project = {}  # backing store for project property
        self._project_rev = 0  # increments on every project set (UI sync guard)
        # Startup uses the canonical release policy: restore a recovery snapshot
        # if one exists, otherwise build the clean default project. Developers can
        # still force a clean boot with MODULO_START_CLEAN=1.
        self.startup_source = "unknown"
        self.startup_recovery_status = {}
        try:
            startup_bundle = build_startup_bundle(
                bypass_era=str(os.environ.get('MODULO_BYPASS_ERA', '')).strip().lower() in {'1','true','yes','on'}
            )
            startup_project = startup_bundle.get("project") if isinstance(startup_bundle, dict) else {}
            self.startup_source = str((startup_bundle or {}).get("source") or "unknown")
            recovery_status = (startup_bundle or {}).get("recovery") if isinstance(startup_bundle, dict) else {}
            self.startup_recovery_status = recovery_status if isinstance(recovery_status, dict) else {}
            self._project = _sync_project_manager_startup_state(self.pm, startup_project if isinstance(startup_project, dict) else {})
            self._last_validation = getattr(self.pm, "_last_validation", {"ok": True, "errors": [], "warnings": []})
            self._project_rev = 1 if isinstance(self._project, dict) else 0
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

        self._selection_indices: list[int] = []
        self._full_preview_engine = None
        self._full_preview_geom = None
        self._full_preview_audio = None
        # When True, the next preview paint will sync engine.project from project dict.
        self._preview_dirty = True
        self._export_target_id = "arduino_avr_fastled_msgeq7"

        # Signal bus state for diagnostics and runtime evaluation.
        self.signal_bus = SignalBus()
        self.signals = {}  # latest SignalBus snapshot for diagnostics/rules (dict)
        # Engine-owned always-on audio service.
        self.audio_service = AudioService()
        # PreviewEngine consumes the backend object directly (.step() / .state).
        self._full_preview_audio = getattr(self.audio_service, "backend", None)
        self.preview_audio = self._full_preview_audio
        self.preview_audio_mode = getattr(self.audio_service, "mode", "sim")
        self.preview_audio_backend = getattr(self.audio_service, "backend_name", type(self._full_preview_audio).__name__ if self._full_preview_audio is not None else "AudioSim")
        self.preview_audio_status = getattr(self.audio_service, "status", "OK")
        self.preview_audio_last_error = getattr(self.audio_service, "last_error", "")
        self._signal_last_t = None  # type: float | None
        self._signal_frame = 0

        # Preview-time playlist state.
        # Stored configuration lives in ~/.modulo/presets.json (presets) and UI session state (playlist entries).
        try:
            from runtime.playlist_player import PlaylistPlayer
            self._playlist_player = PlaylistPlayer()
            self._playlist_entries = []  # list[dict]
        except Exception:
            self._playlist_player = None
            self._playlist_entries = []
        self._playlist_enabled = False

        # Phase 6.2/6.3: Variables + Rules runtime state (kept runtime to avoid project churn).
        try:
            v0 = get_variables_state(self._project)
            self._variables_state = v0 if isinstance(v0, dict) else {"number": {}, "toggle": {}}
        except Exception:
            self._variables_state = {"number": {}, "toggle": {}}
        self._rules_prev_state: dict = {}
        self._rules_last_apply_t: float = 0.0

        # Variables persistence policy:
        # - project['variables'] are defaults (authored, saved)
        # - self._variables_state is runtime (mutated by Rules)
        # Runtime state is NOT auto-written back to project.
        self._variables_rev: int = 0
        self._variables_runtime_dirty: bool = False

        # Ensure preview engine/geometry are ready on startup so the UI can render immediately.
        # (Some UI paths lazily rebuild, but blank startup makes diagnosis harder.)
        try:
            self._rebuild_full_preview_engine()
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
            pass

    # ---- Phase 6.1: signal bus surface ----



    # ---- Era system ----


    # ---- core project surface expected by qt_app.py ----
    # ---- core project surface expected by qt_app.py ----
    # ---- preview ----

    # ---------------------------
    # Playlist (preview-time)
    # ---------------------------



