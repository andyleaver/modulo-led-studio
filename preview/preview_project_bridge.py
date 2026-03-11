from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
from typing import Any

from app.json_sanitize import sanitize_for_json
from app.project_canonical import canonicalize_project_dict


def _preview_temp_dir(root_dir: str | None) -> Path | None:
    if not root_dir:
        return None
    root_path = Path(root_dir).resolve()
    artifact_root = Path(os.environ.get("MODULO_ARTIFACT_DIR", root_path.parent / "artifacts"))
    tmp_dir = artifact_root / "preview_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def prepare_preview_project(project_dict: dict, *, root_dir: str | None = None) -> tuple[object, list, dict]:
    """Return ``(project_model, sanitize_issues, clean_proj)`` for preview use.

    This is the single canonical dict -> preview-model bridge used by Qt preview,
    diagnostics, and standalone preview probes.
    """
    from models.io import load_project

    canonical_proj, _ = canonicalize_project_dict(project_dict or {})
    clean_proj, sanitize_issues = sanitize_for_json(canonical_proj or {})

    tmp_dir = _preview_temp_dir(root_dir)
    fd, tmp = tempfile.mkstemp(
        prefix="modulo_preview_",
        suffix=".json",
        dir=str(tmp_dir) if tmp_dir is not None else None,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean_proj, f, indent=2)
        project_model = load_project(tmp)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return project_model, sanitize_issues, clean_proj


def make_preview_engine_from_project_dict(
    project_dict: dict,
    *,
    audio: Any = None,
    signal_bus: Any = None,
    fixed_dt: float = 1.0 / 60.0,
    root_dir: str | None = None,
):
    """Build a PreviewEngine through the canonical preview-project bridge."""
    from preview.preview_engine import PreviewEngine

    project_model, sanitize_issues, clean_proj = prepare_preview_project(project_dict, root_dir=root_dir)
    eng = PreviewEngine(project=project_model, audio=audio, fixed_dt=fixed_dt, signal_bus=signal_bus)
    try:
        eng.project_data = clean_proj
    except Exception:
        pass
    try:
        eng._sanitize_issues = list(sanitize_issues or [])
    except Exception:
        pass
    return eng, sanitize_issues, clean_proj
