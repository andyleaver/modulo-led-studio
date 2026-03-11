"""Startup/bootstrap helpers for CoreBridge."""

from __future__ import annotations

import uuid

from app.project_canonical import apply_project_root, finalize_project_dict
from app.project_manager_normalization import migrate_project_dict
from app.project_model import build_surface_dict
from app.autosave import get_recovery_status, read_autosave_with_meta
from qt.core_bridge_flags import ERA_ENFORCEMENT_DISABLED

def build_clean_start_project(*, bypass_era: bool = False) -> dict:
    """Return the authoritative clean-start project used on app launch."""
    project = {
        "surface": build_surface_dict(kind="strip", count=144),
        "layers": [],
        "rules": [],
        "variables": {"number": {}, "toggle": {}},
        "audio": {},
        "export": {"hw": {"data_pin": 6}},
        "postfx": {},
        "ui": {
            "selected_layer": -1,
            "apply_era_template_on_boot": False,
            "era_template_applied": True,
        },
    }
    if bypass_era:
        ui = {
            **dict(project.get("ui") or {}),
            "era_id": "era_now",
            "era_complete": True,
            "era_done": {"era_now": True},
        }
        project, _validation, _changes = apply_project_root(project, "ui", ui)
    return project



def finalize_startup_project(project: dict) -> tuple[dict, dict]:
    """Run startup projects through the same canonical finalize/validate path as live edits."""
    base = project if isinstance(project, dict) else {}
    try:
        hydrated, validation, _changes = finalize_project_dict(
            base,
            sanitize_for_era=(not ERA_ENFORCEMENT_DISABLED),
            enforce_era=(not ERA_ENFORCEMENT_DISABLED),
            validate=True,
        )
        return hydrated if isinstance(hydrated, dict) else {}, validation if isinstance(validation, dict) else {"ok": True, "errors": [], "warnings": []}
    except Exception:
        fallback = migrate_project_dict(base)
        return fallback if isinstance(fallback, dict) else {}, {"ok": True, "errors": [], "warnings": []}

def ensure_layer_uids(proj: dict) -> None:
    """Ensure each layer dict has a stable uid field for preview state persistence."""
    try:
        layers = proj.get("layers")
        if not isinstance(layers, list):
            return
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            uid = layer.get("uid") or layer.get("__uid")
            if not isinstance(uid, str) or not uid.strip():
                uid = uuid.uuid4().hex
            layer["uid"] = uid
            layer["__uid"] = uid
    except Exception:
        return



def sync_project_manager_startup_state(pm, project: dict) -> dict:
    """Align ProjectManager with startup project without marking it dirty.

    Startup restore/clean boot should not immediately become an unsaved mutation.
    We run the launch payload through the same canonical finalize/validate path
    as live project edits, ensure stable layer ids, and then assign the hydrated
    project directly onto the manager instead of routing through ``pm.set()``,
    which is the edit-time path and intentionally marks the project dirty.
    """
    hydrated, validation = finalize_startup_project(project if isinstance(project, dict) else {})
    ensure_layer_uids(hydrated)
    try:
        pm.project = hydrated
        pm.path = None
        pm.dirty = False
        pm._last_validation = validation
    except Exception:
        pass
    return hydrated

def build_startup_bundle(*, bypass_era: bool = False) -> dict:
    """Return startup project plus lightweight provenance for diagnostics.

    The bundle is intentionally small and stable so diagnostics can tell whether
    launch restored recovery or started clean without re-implementing startup
    policy elsewhere.
    """
    status = get_recovery_status()
    recovered, recovery_meta = read_autosave_with_meta()
    if isinstance(recovered, dict) and recovered:
        source = "recovery_backup" if bool((recovery_meta or {}).get("used_backup")) else "recovery"
        try:
            project = migrate_project_dict(recovered)
        except Exception:
            project = recovered
        if isinstance(status, dict):
            status = {**status, "used_source": str((recovery_meta or {}).get("source") or "none"), "used_path": str((recovery_meta or {}).get("path") or "")}
        return {
            "project": project,
            "source": source,
            "recovery": status,
        }
    source = "clean_forced" if bool(status.get("start_clean")) else "clean_default"
    return {
        "project": build_clean_start_project(bypass_era=bypass_era),
        "source": source,
        "recovery": status,
    }


def build_startup_project(*, bypass_era: bool = False) -> dict:
    """Return recovery snapshot if present, otherwise the canonical clean-start project."""
    bundle = build_startup_bundle(bypass_era=bypass_era)
    project = bundle.get("project")
    return project if isinstance(project, dict) else build_clean_start_project(bypass_era=bypass_era)
