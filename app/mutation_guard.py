from __future__ import annotations
import os
from pathlib import Path

try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="PROJECT", code="MUTATION_GUARD_EXCEPTION", summary=where)
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
MARKER_FILE = ROOT / "MUTATION_GUARD"

def is_enabled() -> bool:
    return MARKER_FILE.exists() or os.environ.get("MUTATION_GUARD") == "1"

def is_frozen() -> bool:
    return is_enabled()

def explain() -> str:
    return "Mutation guard is enabled: mutation actions are disabled (scaffold, promote, update goldens)."

def enable():
    try:
        MARKER_FILE.write_text("1")
    except Exception as e:
        _diag_exc(e, "app/mutation_guard.py")

def disable():
    try:
        if MARKER_FILE.exists():
            MARKER_FILE.unlink()
    except Exception as e:
        _diag_exc(e, "app/mutation_guard.py")
