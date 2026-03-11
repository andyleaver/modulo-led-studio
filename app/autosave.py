from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable

from app.json_sanitize import sanitize_for_json

try:
    from runtime.diagnostics import GLOBAL_DIAGS
except Exception:
    GLOBAL_DIAGS = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
USER_DATA = ROOT / "user_data"
AUTOSAVE = USER_DATA / "autosave_project.json"
BACKUP = USER_DATA / "autosave_project.prev.json"
SNAPSHOT_TYPE = "modulo_recovery_v1"
_LAST_WRITTEN_DIGEST: str | None = None


def _ensure_user_data_dir() -> Path:
    USER_DATA.mkdir(exist_ok=True)
    return USER_DATA


def _env_flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


# Final-release policy:
# - recovery is enabled by default
# - developers can force clean startup / disable recovery via env flags
#   MODULO_RECOVERY_ENABLED=0  -> disables reads + writes
#   MODULO_START_CLEAN=1       -> ignore recovery snapshot on startup
AUTOSAVE_ENABLED = _env_flag("MODULO_RECOVERY_ENABLED", True)


def _diag_exc(exc: Exception, *, code: str, summary: str) -> None:
    try:
        if GLOBAL_DIAGS:
            GLOBAL_DIAGS.exception(exc, domain="PROJECT", code=code, summary=summary)
    except Exception:
        pass


def _wrap_snapshot(project: dict) -> dict:
    clean, _issues = sanitize_for_json(project if isinstance(project, dict) else {})
    return {
        "type": SNAPSHOT_TYPE,
        "project": clean,
    }


def _extract_snapshot_project(payload: Any) -> dict | None:
    if isinstance(payload, dict) and payload.get("type") == SNAPSHOT_TYPE:
        project = payload.get("project")
        return project if isinstance(project, dict) else None
    if isinstance(payload, dict):
        # Back-compat with earlier direct-project autosave files.
        return payload
    return None


def write_autosave(project: dict) -> None:
    global _LAST_WRITTEN_DIGEST
    if not AUTOSAVE_ENABLED:
        return
    try:
        _ensure_user_data_dir()
        payload = _wrap_snapshot(project)
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        digest = str(hash(serialized))
        if digest == _LAST_WRITTEN_DIGEST and AUTOSAVE.exists():
            return
        if AUTOSAVE.exists():
            try:
                current = AUTOSAVE.read_text(encoding="utf-8", errors="ignore")
                if current == serialized:
                    _LAST_WRITTEN_DIGEST = digest
                    return
                BACKUP.write_text(current, encoding="utf-8")
            except Exception as exc:
                _diag_exc(exc, code="AUTOSAVE_BACKUP_FAIL", summary="recovery backup write failed")
        tmp = AUTOSAVE.with_suffix(".tmp")
        tmp.write_text(serialized, encoding="utf-8")
        tmp.replace(AUTOSAVE)
        _LAST_WRITTEN_DIGEST = digest
    except Exception as exc:
        _diag_exc(exc, code="AUTOSAVE_OP_FAIL", summary="recovery snapshot write failed")


def _iso_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def _read_snapshot_file(path: Path) -> dict | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _extract_snapshot_project(payload)


def read_autosave_with_meta() -> tuple[dict | None, dict]:
    meta = {
        "source": "none",
        "path": "",
        "used_backup": False,
    }
    if not AUTOSAVE_ENABLED:
        meta["source"] = "disabled"
        return None, meta
    if _env_flag("MODULO_START_CLEAN", False):
        meta["source"] = "clean_forced"
        return None, meta
    for candidate, source in ((AUTOSAVE, "primary"), (BACKUP, "backup")):
        if not candidate.exists():
            continue
        try:
            project = _read_snapshot_file(candidate)
            if isinstance(project, dict):
                meta["source"] = source
                meta["path"] = str(candidate)
                meta["used_backup"] = bool(source == "backup")
                return project, meta
        except Exception as exc:
            _diag_exc(exc, code="AUTOSAVE_READ_FAIL", summary="recovery snapshot read failed")
    return None, meta


def read_autosave() -> dict | None:
    project, _meta = read_autosave_with_meta()
    return project


def clear_autosave() -> None:
    global _LAST_WRITTEN_DIGEST
    try:
        for candidate in (AUTOSAVE, BACKUP):
            if candidate.exists():
                candidate.unlink()
        _LAST_WRITTEN_DIGEST = None
    except Exception as exc:
        _diag_exc(exc, code="AUTOSAVE_OP_FAIL", summary="recovery snapshot clear failed")


def get_recovery_status() -> dict:
    """Return lightweight recovery state for diagnostics/startup decisions."""
    primary_exists = bool(AUTOSAVE.exists())
    backup_exists = bool(BACKUP.exists())
    return {
        "enabled": bool(AUTOSAVE_ENABLED),
        "start_clean": bool(_env_flag("MODULO_START_CLEAN", False)),
        "primary_exists": primary_exists,
        "backup_exists": backup_exists,
        "primary_path": str(AUTOSAVE),
        "backup_path": str(BACKUP),
        "primary_mtime": _iso_mtime(AUTOSAVE) if primary_exists else "",
        "backup_mtime": _iso_mtime(BACKUP) if backup_exists else "",
    }


class AutoSaver:
    def __init__(self, tk_root, get_project: Callable[[], dict], *, interval_ms: int = 15000):
        self.root = tk_root
        self.get_project = get_project
        self.interval_ms = max(3000, int(interval_ms))
        self._after = None
        self._last_hash = None

    def start(self):
        if not AUTOSAVE_ENABLED:
            return
        self.stop()
        self._tick()

    def stop(self):
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except Exception as exc:
                _diag_exc(exc, code="AUTOSAVE_AFTER_CANCEL_FAIL", summary="recovery after_cancel failed")
            self._after = None

    def _tick(self):
        try:
            proj = self.get_project()
            clean, _issues = sanitize_for_json(proj)
            h = hash(json.dumps(clean, sort_keys=True))
            if h != self._last_hash:
                write_autosave(clean)
                self._last_hash = h
        except Exception as exc:
            _diag_exc(exc, code="AUTOSAVE_TICK_FAIL", summary="recovery snapshot tick failed")
        self._after = self.root.after(self.interval_ms, self._tick)
