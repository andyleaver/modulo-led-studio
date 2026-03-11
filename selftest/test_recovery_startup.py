from __future__ import annotations

import importlib
from pathlib import Path


def _configure_recovery_paths(tmp_path: Path):
    import app.autosave as autosave

    autosave.AUTOSAVE = tmp_path / "autosave_project.json"
    autosave.BACKUP = tmp_path / "autosave_project.prev.json"
    autosave.AUTOSAVE_ENABLED = True
    return autosave


def test_project_manager_new_hard_resets_and_clears_recovery(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    from app.project_manager import ProjectManager

    pm = ProjectManager()
    pm.guarded_add_layer({"behavior": "solid", "params": {"color": [255, 0, 0]}})
    assert len(pm.project.get("layers") or []) == 1
    assert autosave.AUTOSAVE.exists()

    pm.new()

    assert pm.path is None
    assert pm.dirty is False
    assert (pm.project.get("layers") or []) == []
    surface = pm.project.get("surface") or {}
    assert surface.get("kind") == "strip"
    assert int(surface.get("count") or 0) == 144
    assert not autosave.AUTOSAVE.exists()


def test_save_clears_recovery_snapshot(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    from app.project_manager import ProjectManager

    pm = ProjectManager()
    pm.guarded_add_layer({"behavior": "solid", "params": {"level": 1.0}})
    assert autosave.AUTOSAVE.exists()

    saved = pm.save(tmp_path / "project.json")

    assert saved.exists()
    assert not autosave.AUTOSAVE.exists()
    assert pm.dirty is False


def test_startup_restores_recovery_snapshot_and_clean_override(tmp_path: Path, monkeypatch) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave(
        {
            "surface": {"kind": "strip", "count": 16, "width": 16, "height": 1, "mapping": {"kind": "strip", "serpentine": False}},
            "layers": [{"behavior": "solid", "params": {"level": 0.5}}],
            "rules": [],
            "variables": {"number": {}, "toggle": {}},
            "audio": {},
            "export": {"hw": {"data_pin": 6}},
            "postfx": {},
            "ui": {"selected_layer": 0},
        }
    )

    import qt.core_bridge_startup as startup
    importlib.reload(startup)

    restored = startup.build_startup_project()
    assert len(restored.get("layers") or []) == 1
    surface = restored.get("surface") or {}
    assert int(surface.get("count") or 0) == 16

    monkeypatch.setenv("MODULO_START_CLEAN", "1")
    importlib.reload(startup)
    clean = startup.build_startup_project()
    clean_surface = clean.get("surface") or {}
    assert (clean.get("layers") or []) == []
    assert int(clean_surface.get("count") or 0) == 144


def test_read_autosave_falls_back_to_backup_and_clear_removes_both(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.BACKUP.write_text(
        """{
  "type": "modulo_recovery_v1",
  "project": {"surface": {"kind": "strip", "count": 24}, "layers": []}
}""",
        encoding="utf-8",
    )
    autosave.AUTOSAVE.write_text('{not-json', encoding="utf-8")

    restored = autosave.read_autosave()

    assert isinstance(restored, dict)
    surface = restored.get("surface") or {}
    assert int(surface.get("count") or 0) == 24

    autosave.clear_autosave()
    assert not autosave.AUTOSAVE.exists()
    assert not autosave.BACKUP.exists()


def test_startup_sync_keeps_project_manager_clean_and_assigns_uids(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave(
        {
            "surface": {"kind": "strip", "count": 12, "width": 12, "height": 1, "mapping": {"kind": "strip", "serpentine": False}},
            "layers": [{"behavior": "solid", "params": {"level": 0.8}}],
            "rules": [],
            "variables": {"number": {}, "toggle": {}},
            "audio": {},
            "export": {"hw": {"data_pin": 6}},
            "postfx": {},
            "ui": {"selected_layer": 0},
        }
    )

    import qt.core_bridge_startup as startup
    importlib.reload(startup)
    from app.project_manager import ProjectManager

    pm = ProjectManager()
    recovered = startup.build_startup_project()
    hydrated = startup.sync_project_manager_startup_state(pm, recovered)

    assert pm.dirty is False
    assert pm.path is None
    assert pm.project is hydrated
    assert len(pm.project.get("layers") or []) == 1
    layer = (pm.project.get("layers") or [])[0]
    assert isinstance(layer.get("uid"), str) and layer.get("uid")
    assert layer.get("__uid") == layer.get("uid")
    assert autosave.AUTOSAVE.exists()


def test_identical_recovery_write_is_deduped_without_rotating_backup(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    project = {
        "surface": {"kind": "strip", "count": 24, "width": 24, "height": 1, "mapping": {"kind": "strip", "serpentine": False}},
        "layers": [{"behavior": "solid", "params": {"level": 0.2}}],
        "rules": [],
        "variables": {"number": {}, "toggle": {}},
        "audio": {},
        "export": {"hw": {"data_pin": 6}},
        "postfx": {},
        "ui": {"selected_layer": 0},
    }

    autosave.write_autosave(project)
    first = autosave.AUTOSAVE.read_text(encoding="utf-8")
    assert autosave.AUTOSAVE.exists()
    assert not autosave.BACKUP.exists()

    autosave.write_autosave(project)

    assert autosave.AUTOSAVE.read_text(encoding="utf-8") == first
    assert not autosave.BACKUP.exists()


def test_clear_autosave_still_removes_stale_snapshots_when_recovery_disabled(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave({"surface": {"kind": "strip", "count": 8}, "layers": []})
    autosave.BACKUP.write_text(autosave.AUTOSAVE.read_text(encoding="utf-8"), encoding="utf-8")
    assert autosave.AUTOSAVE.exists()
    assert autosave.BACKUP.exists()

    autosave.AUTOSAVE_ENABLED = False
    autosave.clear_autosave()

    assert not autosave.AUTOSAVE.exists()
    assert not autosave.BACKUP.exists()


def test_get_recovery_status_reports_presence_and_flags(tmp_path: Path, monkeypatch) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave({"surface": {"kind": "strip", "count": 10}, "layers": []})
    autosave.BACKUP.write_text(autosave.AUTOSAVE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("MODULO_START_CLEAN", "1")

    status = autosave.get_recovery_status()

    assert status["enabled"] is True
    assert status["start_clean"] is True
    assert status["primary_exists"] is True
    assert status["backup_exists"] is True
    assert status["primary_path"].endswith("autosave_project.json")
    assert status["backup_path"].endswith("autosave_project.prev.json")


def test_build_startup_bundle_reports_source_and_recovery_status(tmp_path: Path, monkeypatch) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave({"surface": {"kind": "strip", "count": 14}, "layers": [{"behavior": "solid", "params": {}}]})

    import qt.core_bridge_startup as startup
    importlib.reload(startup)

    bundle = startup.build_startup_bundle()
    assert bundle["source"] == "recovery"
    assert isinstance(bundle["project"], dict)
    assert bundle["recovery"]["primary_exists"] is True

    monkeypatch.setenv("MODULO_START_CLEAN", "1")
    importlib.reload(startup)
    clean_bundle = startup.build_startup_bundle()
    assert clean_bundle["source"] == "clean_forced"
    assert (clean_bundle["project"].get("layers") or []) == []
    assert clean_bundle["recovery"]["start_clean"] is True


def test_read_autosave_with_meta_reports_backup_source_when_primary_corrupt(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.AUTOSAVE.write_text('{broken', encoding='utf-8')
    autosave.BACKUP.write_text(
        '{"type": "modulo_recovery_v1", "project": {"surface": {"kind": "strip", "count": 33}, "layers": []}}',
        encoding='utf-8',
    )

    restored, meta = autosave.read_autosave_with_meta()

    assert isinstance(restored, dict)
    assert int(((restored.get("surface") or {}).get("count") or 0)) == 33
    assert meta["source"] == "backup"
    assert meta["used_backup"] is True
    assert meta["path"].endswith("autosave_project.prev.json")


def test_build_startup_bundle_marks_backup_restore_and_used_source(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.AUTOSAVE.write_text('{broken', encoding='utf-8')
    autosave.BACKUP.write_text(
        '{"type": "modulo_recovery_v1", "project": {"surface": {"kind": "strip", "count": 19}, "layers": [{"behavior": "solid", "params": {}}]}}',
        encoding='utf-8',
    )

    import qt.core_bridge_startup as startup
    importlib.reload(startup)

    bundle = startup.build_startup_bundle()

    assert bundle["source"] == "recovery_backup"
    assert bundle["recovery"]["used_source"] == "backup"
    assert bundle["recovery"]["used_path"].endswith("autosave_project.prev.json")
    assert isinstance(bundle["recovery"].get("backup_mtime"), str)
    assert len(bundle["project"].get("layers") or []) == 1


def test_health_check_reports_live_recovery_presence_but_keeps_startup_provenance(tmp_path: Path) -> None:
    autosave = _configure_recovery_paths(tmp_path)
    autosave.write_autosave({"surface": {"kind": "strip", "count": 18}, "layers": []})

    class _Holder:
        startup_source = "recovery"
        startup_recovery_status = {
            "enabled": True,
            "start_clean": False,
            "primary_exists": True,
            "backup_exists": False,
            "used_source": "primary",
            "used_path": str(autosave.AUTOSAVE),
            "primary_path": str(autosave.AUTOSAVE),
            "backup_path": str(autosave.BACKUP),
        }

    from app.project_diagnostics_health import run_full_health_check

    report_before = run_full_health_check({}, controller=_Holder(), include_audio=False)
    assert "startup_source: recovery" in report_before
    assert "recovery.primary_exists: True" in report_before
    assert "recovery.used_source: primary" in report_before

    autosave.clear_autosave()
    report_after = run_full_health_check({}, controller=_Holder(), include_audio=False)

    assert "startup_source: recovery" in report_after
    assert "recovery.primary_exists: False" in report_after
    assert "recovery.backup_exists: False" in report_after
    assert "recovery.used_source: primary" in report_after


def test_startup_sync_runs_finalize_validation_path(tmp_path: Path) -> None:
    _configure_recovery_paths(tmp_path)
    import qt.core_bridge_startup as startup
    importlib.reload(startup)
    from app.project_manager import ProjectManager

    pm = ProjectManager()
    recovered = {
        "surface": {"shape": "cells", "width": 8, "height": 4, "mapping": {"serpentine": True}},
        "layers": [{"behavior": "solid", "blend": "add"}],
        "ui": {},
    }

    hydrated = startup.sync_project_manager_startup_state(pm, recovered)

    surface = hydrated.get("surface") or {}
    layer = (hydrated.get("layers") or [{}])[0]
    assert surface.get("kind") == "cells"
    assert "shape" not in surface
    assert int(surface.get("width") or 0) == 8
    assert int(surface.get("height") or 0) == 4
    assert (surface.get("mapping") or {}).get("serpentine") is True
    assert layer.get("blend_mode") == "add"
    assert "blend" not in layer
    assert isinstance(getattr(pm, "_last_validation", None), dict)
    assert pm._last_validation.get("ok") is True
