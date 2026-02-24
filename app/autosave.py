from __future__ import annotations
import time, json
from pathlib import Path
from typing import Callable, Any

from app.json_sanitize import sanitize_for_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
AUTOSAVE = OUT / "autosave_project.json"
BACKUP = OUT / "autosave_project.prev.json"

# ------------------------------------------------------------
# HARD DISABLE (Release safety)
#
# Autosave/restore has been the primary source of destructive startup
# mutations and UI/preview desync during HUB75/matrix work.
#
# Policy for now:
#   - No implicit restore on startup
#   - No implicit writes in the background or on exit
#
# Keep the implementation present for future re-enable behind an
# explicit user action / settings flag.
# ------------------------------------------------------------
AUTOSAVE_ENABLED = False

def write_autosave(project: dict) -> None:
    if not AUTOSAVE_ENABLED:
        return
    try:
        if AUTOSAVE.exists():
            try:
                BACKUP.write_text(AUTOSAVE.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            except Exception:
                pass
        clean, _issues = sanitize_for_json(project)
        AUTOSAVE.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    except Exception:
        pass

def read_autosave() -> dict | None:
    if not AUTOSAVE_ENABLED:
        return None
    if not AUTOSAVE.exists():
        return None
    try:
        return json.loads(AUTOSAVE.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear_autosave() -> None:
    if not AUTOSAVE_ENABLED:
        return
    try:
        if AUTOSAVE.exists():
            AUTOSAVE.unlink()
    except Exception:
        pass

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
            try: self.root.after_cancel(self._after)
            except Exception: pass
            self._after = None

    def _tick(self):
        try:
            proj = self.get_project()
            clean, _issues = sanitize_for_json(proj)
            h = hash(json.dumps(clean, sort_keys=True))
            if h != self._last_hash:
                write_autosave(clean)
                self._last_hash = h
        except Exception:
            pass
        self._after = self.root.after(self.interval_ms, self._tick)
