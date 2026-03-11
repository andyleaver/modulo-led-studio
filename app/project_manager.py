from __future__ import annotations

import json
from pathlib import Path

from app.json_sanitize import sanitize_for_json
from app.project_defaults import DEFAULT_PROJECT
from app.autosave import clear_autosave, write_autosave
from app.project_manager_diagnostics import project_manager_diag_exc
from app.project_manager_layers import bind_project_manager_layer_methods
from app.project_canonical import apply_project_root
from app.project_manager_normalization import migrate_project_dict

ROOT = Path(__file__).resolve().parents[1]
USER_DATA = ROOT / "user_data"


def _ensure_user_data_dir() -> Path:
    USER_DATA.mkdir(exist_ok=True)
    return USER_DATA

_pm_diag_exc = project_manager_diag_exc


class ProjectManager:
    def __init__(self):
        self.project: dict = json.loads(json.dumps(DEFAULT_PROJECT))
        self.path: Path | None = None
        self.dirty: bool = False
        self._listeners = []
        self.root_dir = str(ROOT)

    def add_listener(self, fn):
        try:
            self._listeners.append(fn)
        except Exception as exc:
            _pm_diag_exc(exc, "add_listener")

    def _write_recovery_snapshot(self):
        try:
            if bool(self.dirty):
                write_autosave(self.project if isinstance(self.project, dict) else {})
        except Exception as exc:
            _pm_diag_exc(exc, "write_recovery_snapshot")

    def _notify(self):
        self._write_recovery_snapshot()
        for fn in list(self._listeners):
            try:
                fn(self)
            except Exception as exc:
                try:
                    from runtime.diagnostics import GLOBAL_DIAGS
                    GLOBAL_DIAGS.exception(
                        exc,
                        domain="PROJECT",
                        code="LISTENER_EXCEPTION",
                        summary="project listener exception",
                        details={"file": "app/project_manager.py"},
                    )
                except Exception:
                    pass

    def get(self) -> dict:
        return self.project

    def set(self, project_dict: dict):
        self.project = migrate_project_dict(project_dict)
        self.dirty = True
        self._notify()

    def mark_clean(self):
        self.dirty = False
        try:
            clear_autosave()
        except Exception as exc:
            _pm_diag_exc(exc, "clear_recovery_on_mark_clean")
        self._notify()

    def display_path(self) -> str:
        return str(self.path) if self.path else "(not saved yet)"

    def _apply_export_defaults_from_target(self):
        """Normalize default export config to match selected target pack defaults."""
        try:
            from export.targets.registry import (
                resolve_requested_audio_hw,
                resolve_requested_backends,
                resolve_requested_hw,
                resolve_target_meta,
            )
            project = self.project or {}
            export_cfg = project.get("export") or {}
            target_id = export_cfg.get("target_id") or export_cfg.get("target") or "arduino_uno_fastled_msgeq7"
            target_meta = resolve_target_meta(str(target_id))
            selected = resolve_requested_backends(project, target_meta)
            export_cfg["target_id"] = str(target_meta.get("id") or target_id)
            export_cfg["led_backend"] = selected.get("led_backend")
            export_cfg["audio_backend"] = selected.get("audio_backend")
            export_cfg["hw"] = resolve_requested_hw(project, target_meta)
            export_cfg["audio_hw"] = resolve_requested_audio_hw(project, target_meta)
            project, _snap, _changes = apply_project_root(project, "export", export_cfg)
            self.project = project
        except Exception as exc:
            _pm_diag_exc(exc, "apply_export_defaults_from_target")

    def new(self):
        project = migrate_project_dict(json.loads(json.dumps(DEFAULT_PROJECT)))
        self.project = project
        self._apply_export_defaults_from_target()
        self.path = None
        self.dirty = False
        try:
            clear_autosave()
        except Exception as exc:
            _pm_diag_exc(exc, "clear_recovery_on_new")
        self._notify()

    def load(self, path: Path):
        self.project = migrate_project_dict(json.loads(path.read_text(encoding="utf-8")))
        self.path = path
        self.dirty = False
        try:
            clear_autosave()
        except Exception as exc:
            _pm_diag_exc(exc, "clear_recovery_on_load")
        self._notify()

    def save(self, path: Path | None = None):
        if path is not None:
            self.path = path
        if self.path is None:
            self.path = _ensure_user_data_dir() / "last_project.json"
        clean, _issues = sanitize_for_json(self.project)
        self.path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
        self.dirty = False
        try:
            clear_autosave()
        except Exception as exc:
            _pm_diag_exc(exc, "clear_recovery_on_save")
        self._notify()
        return self.path

    def load_project_dict(self, project_dict: dict):
        if not isinstance(project_dict, dict):
            return
        self.project = migrate_project_dict(project_dict)
        self.dirty = True
        self._notify()

    def load_fixture(self, filename: str):
        try:
            from models.io import load_project
            path = ROOT / "fixtures" / "projects" / filename
            project = load_project(path)
            self.project = project.to_dict()
            self.dirty = True
            self._notify()
        except Exception:
            return

    def apply_audio_preset(self, preset_filename: str):
        try:
            from runtime.resolver import set_address
            from app.project_normalize import normalize_project_zones_masks_groups
            preset_path = ROOT / "fixtures" / "audio_presets" / preset_filename
            raw = json.loads(preset_path.read_text(encoding="utf-8"))
            data, _changes = normalize_project_zones_masks_groups(raw)
            audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
            routes = list(audio.get("routes") or []) if isinstance(audio.get("routes"), list) else []
            preset_name = str(audio.get("preset_name") or data.get("name") or preset_filename)
            if not isinstance(self.project, dict):
                return
            project_now = self.project
            changed = False
            project_new, did_change = set_address(project=project_now, address="project.audio.routes", value=routes)
            if did_change:
                project_now = project_new
                changed = True
            project_new, did_change = set_address(project=project_now, address="project.audio.preset_name", value=preset_name)
            if did_change:
                project_now = project_new
                changed = True
            if not changed:
                return
            self.project = project_now
            self.dirty = True
            self._notify()
        except Exception as exc:
            _pm_diag_exc(exc, "apply_audio_preset", {"preset_filename": str(preset_filename)})


bind_project_manager_layer_methods(ProjectManager)
