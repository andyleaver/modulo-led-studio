from __future__ import annotations

def run() -> tuple[bool, str]:
    try:
        import json
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        # try last_project first, else a shipped canonical fixture
        cand = [
            repo / "user_data" / "last_project.json",
            repo / "fixtures" / "projects" / "order_pipeline_lock.json",
        ]
        proj = None
        for c in cand:
            if c.is_file():
                try:
                    proj = json.loads(c.read_text(encoding="utf-8"))
                    break
                except Exception:
                    continue
        if not isinstance(proj, dict):
            return True, "no project found to scan (ok)"
        layers = proj.get("layers") or []
        if not isinstance(layers, list):
            return True, "no layers (ok)"
        for i, L0 in enumerate(layers):
            L = L0 if isinstance(L0, dict) else {}
            if "blend" in L:
                return False, f"shadow key present: layer[{i}].blend"
        return True, "ok"
    except Exception as e:
        return False, f"exception: {e}"
