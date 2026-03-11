from __future__ import annotations

from pathlib import Path

APP_ID = "MODULO_LED_STUDIO"

def get_app_id(repo_root: str | Path | None = None) -> str:
    """Return the packaged application identifier from APP_ID.txt when available."""
    try:
        root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
        app_id_path = root / "APP_ID.txt"
        if app_id_path.is_file():
            app_id = app_id_path.read_text(encoding="utf-8").strip()
            if app_id:
                return app_id
    except Exception:
        pass
    return APP_ID
