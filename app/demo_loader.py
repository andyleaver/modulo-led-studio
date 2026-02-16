from __future__ import annotations
import json
from pathlib import Path

def load_demo_projects() -> list[dict]:
    here = Path(__file__).resolve().parent.parent
    path = here / "demos" / "demo_projects.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
