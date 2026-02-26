from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAG = ROOT / "BETA_FREEZE"

def is_frozen() -> bool:
    # either file exists or env var set
    return FLAG.exists() or os.environ.get("BETA_FREEZE") == "1"

def explain() -> str:
    return "Beta Freeze is enabled: mutation actions are disabled (scaffold/promote/update goldens)."

def enable():
    try:
        FLAG.write_text("1")
    except Exception:
        pass

def disable():
    try:
        if FLAG.exists():
            FLAG.unlink()
    except Exception:
        pass
