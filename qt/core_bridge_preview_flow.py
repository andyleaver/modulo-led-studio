from __future__ import annotations

from app.project_model import get_surface_snapshot
from qt.core_bridge_preview import (
    prepare_preview_project as _prepare_preview_project,
    build_preview_geometry_from_snapshot as _build_preview_geometry_from_snapshot,
    reapply_runtime_only_preview_state as _reapply_runtime_only_preview_state,
)
from qt.core_bridge_startup import ensure_layer_uids as _ensure_layer_uids


class CoreBridgePreviewFlowMixin:
        def _rebuild_full_preview_engine(self):
            """Rebuild full preview renderer from current project (no Tk)."""
            try:
                from preview.preview_project_bridge import make_preview_engine_from_project_dict

                proj_dict = self.project or {}
                _ensure_layer_uids(proj_dict)

                # Preserve engine-owned state (stateful/game effects)
                prev_state_by_uid = {}
                try:
                    prev_state_by_uid = dict(getattr(self._full_preview_engine, "_state_by_uid", {}) or {})
                except Exception:
                    prev_state_by_uid = {}

                _, sanitize_issues, clean_proj = _prepare_preview_project(
                    proj_dict, root_dir=getattr(self.pm, "root_dir", None)
                )
                self._full_preview_sanitize_issues = sanitize_issues
                try:
                    self._full_preview_audio = getattr(getattr(self, "audio_service", None), "backend", None)
                except Exception:
                    self._full_preview_audio = None
                # Prime once so startup health can show non-zero values before the first render tick.
                try:
                    if getattr(self, "audio_service", None) is not None:
                        self.audio_service.step(0.0)
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
                # Expose audio to diagnostics and health checks.
                self.preview_audio = self._full_preview_audio
                try:
                    audio_cfg = (clean_proj.get('audio') or {}) if isinstance(clean_proj, dict) else {}
                    self.preview_audio_mode = str(audio_cfg.get('mode') or getattr(getattr(self, "audio_service", None), "mode", "sim") or 'sim')
                except Exception:
                    self.preview_audio_mode = getattr(getattr(self, "audio_service", None), "mode", "sim") or 'sim'
                self.preview_audio_backend = type(self._full_preview_audio).__name__ if self._full_preview_audio is not None else 'AudioSim'
                self.preview_audio_status = getattr(getattr(self, "audio_service", None), "status", "OK") or 'OK'
                self._full_preview_engine, _, clean_proj = make_preview_engine_from_project_dict(
                    proj_dict,
                    audio=self._full_preview_audio,
                    signal_bus=getattr(self, 'signal_bus', None),
                    root_dir=getattr(self.pm, 'root_dir', None),
                )
                _reapply_runtime_only_preview_state(proj_dict, self._full_preview_engine.project)

                # NOTE: CoreBridge exposes `preview_engine` as a @property returning
                # `_full_preview_engine` and that property has no setter. Assigning to it
                # breaks preview. Always mutate `_full_preview_engine` directly.

                # Keep a live reference to the project dict used to build the engine for diagnostics.
                try:
                    self._full_preview_engine.project_data = clean_proj
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                # Mark preview as needing a sync with the current project after rebuild.
                try:
                    self._preview_dirty = True
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                # Snapshot audio state for the startup health report.
                self._diagnostics_tick_audio()
                # Publish an initial signal snapshot so diagnostics and health panels can
                # display audio.* immediately on startup. SignalBus.update() is
                # keyword-only.
                try:
                    self.signal_bus.update(
                        t=0.0,
                        dt=0.0,
                        frame=0,
                        audio_state=getattr(self._full_preview_audio, 'state', None),
                        variables_state=None,
                        derived_signals={
                            # Canonical derived time signals for Rules (Phase 6.x)
                            'time.square1hz': 1.0,
                            'time.square1hz_inv': 0.0,
                            'time.phase1hz': 0.0,
                        },
                    )
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                # Apply persisted target mask to engine
                try:
                    tm = self.target_mask
                    setattr(self._full_preview_engine, "target_mask", tm)
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                try:
                    if prev_state_by_uid:
                        self._full_preview_engine._state_by_uid.update(prev_state_by_uid)
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                surface_snap = get_surface_snapshot(clean_proj) if isinstance(clean_proj, dict) else {}
                self._full_preview_geom = _build_preview_geometry_from_snapshot(surface_snap)
            except Exception as e:
                # Persist the failure so diagnostics can explain *why* preview is blank.
                try:
                    import traceback as _tb
                    self._full_preview_last_error = f"{type(e).__name__}: {e}"
                    self._full_preview_last_trace = "".join(_tb.format_exc())
                except Exception:
                    self._full_preview_last_error = "(unknown preview rebuild error)"
                    self._full_preview_last_trace = ""
                self._full_preview_engine = None
                self._full_preview_geom = None
                return
            # Last project validation snapshot (Phase A1 lock)
            self._last_validation = {'ok': True, 'errors': [], 'warnings': []}

        def sync_preview_engine_from_project_data(self) -> None:
            """Rebuild PreviewEngine.project from current project_data.

            Contract:
              - UI edits mutate CoreBridge.project (dict).
              - PreviewEngine renders from PreviewEngine.project (models.Project).
              - This function is the single supported bridge between the two.
            """
            # IMPORTANT:
            # The Qt preview widgets render from the *full* preview engine instance
            # (CoreBridge._full_preview_engine). Historically we also exposed a
            # CoreBridge.preview_engine property for diagnostics. These must never
            # diverge, otherwise UI toggles mutate project_data but the renderer
            # keeps using a stale Project model.
            eng = getattr(self, "_full_preview_engine", None) or getattr(self, "preview_engine", None)
            if eng is None:
                return
            if not getattr(self, "project", None):
                return
            try:
                proj_obj, sanitize_issues, clean_proj = _prepare_preview_project(
                    self.project, root_dir=getattr(getattr(self, "pm", None), "root_dir", None)
                )
                try:
                    self._full_preview_sanitize_issues = sanitize_issues
                except Exception:
                    pass
                _reapply_runtime_only_preview_state(self.project, proj_obj)
                # Swap the project object used by the renderer.
                eng.project = proj_obj
                # Optional: keep a reference for diagnostics.
                try:
                    eng.project_data = clean_proj
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

                # Keep legacy attribute aligned if present (some builds expose a separate
                # read-only `preview_engine` property used by diagnostics).
                try:
                    pe = getattr(self, "preview_engine", None)
                    if pe is not None and pe is not eng:
                        pe.project = proj_obj
                        try:
                            pe.project_data = clean_proj
                        except Exception as e:
                            from runtime.diagnostics import GLOBAL_DIAGS
                            GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                            pass
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
                try:
                    self._preview_dirty = False
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
                try:
                    self._preview_sync_last_error = None
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
            except Exception as e:
                # Never crash UI for a preview sync; record for health report.
                try:
                    self._preview_sync_last_error = repr(e)
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

        def rebuild_preview(self, reason: str = "project_mutated") -> None:
            """Public, UI-safe preview refresh (no Apply semantics).

            Policy: keep the existing PreviewEngine instance alive, but replace its
            Project model from current CoreBridge.project dict using the canonical loader.
            This is the same mechanism layout switching relies on, without changing layout.
            """
            try:
                # Mark dirty and resync engine.project from the current dict.
                try:
                    self._preview_dirty = True
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
                self.sync_preview_engine_from_project_data()
            except Exception as e:
                try:
                    self._last_error = f"rebuild_preview(sync): {e!r}"
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

            # Nudge any preview widgets (strip/matrix) if present.
            for attr in ("preview_widget", "matrix_widget", "strip_preview_widget", "matrix_preview_widget"):
                try:
                    w = getattr(self, attr, None)
                    if w is not None and hasattr(w, "update"):
                        w.update()
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

        def rebuild_preview_clean(self, reason: str = "diagnostics_clean") -> None:
            """Rebuild preview with a *fresh* PreviewEngine state.

            Unlike rebuild_preview(), this does NOT preserve any engine-owned temporal
            state (e.g. trail/history buffers). Intended for diagnostics so each run
            starts from a totally blank slate.
            """
            # Mark dirty so any external logic knows we rebuilt.
            try:
                self._preview_dirty = True
            except Exception as e:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                pass

            try:
                from preview.preview_project_bridge import make_preview_engine_from_project_dict
                # Intentionally do NOT preserve prev_state_by_uid, but do keep the
                # canonical dict -> model bridge identical to all other preview rebuilds.
                self._full_preview_audio = getattr(getattr(self, "audio_service", None), "backend", None)
                proj_obj, sanitize_issues, clean_proj = _prepare_preview_project(
                    self.project, root_dir=getattr(getattr(self, "pm", None), "root_dir", None)
                )
                try:
                    self._full_preview_sanitize_issues = sanitize_issues
                except Exception:
                    pass
                _reapply_runtime_only_preview_state(self.project, proj_obj)
                self._full_preview_engine, _, clean_proj = make_preview_engine_from_project_dict(
                    self.project,
                    audio=self._full_preview_audio,
                    signal_bus=getattr(self, 'signal_bus', None),
                    root_dir=getattr(getattr(self, 'pm', None), 'root_dir', None),
                )
                snap = get_surface_snapshot(clean_proj)
                self._full_preview_geom = _build_preview_geometry_from_snapshot(snap)
            except Exception as e:
                try:
                    self._last_error = f"rebuild_preview_clean(engine): {e!r}"
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

            try:
                self.sync_preview_engine_from_project_data()
            except Exception as e:
                try:
                    self._last_error = f"rebuild_preview_clean(sync): {e!r}"
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass

            # Best-effort UI refresh.
            for attr in ("preview_widget", "matrix_widget", "strip_preview_widget", "matrix_preview_widget"):
                try:
                    w = getattr(self, attr, None)
                    if w is not None and hasattr(w, "update"):
                        w.update()
                except Exception as e:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(e, domain="RULES", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"qt/core_bridge.py"})
                    pass
