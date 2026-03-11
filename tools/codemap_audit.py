#!/usr/bin/env python3
"""
Modulo CODEMAP (audited index)
Goal: generate a truthful, code-derived map of where major systems live.
This is NOT a capability claim doc — it's an index into the codebase.
Outputs:
  docs/CODEMAP.md
  docs/CODEMAP.json
"""
from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _ensure_docs_dir() -> Path:
    DOCS.mkdir(exist_ok=True)
    return DOCS

CATEGORIES = [
    ("Boot / Entry", ["modulo_designer.py", "qt/qt_app.py", "qt/main_window.py", "qt/main_layout.py"]),
    ("Qt UI", ["qt/"]),
    ("Preview", ["qt/surface_preview_widget.py", "qt/preview_widgets.py"]),
    ("Core Runtime", ["app_core.py", "core/", "runtime/"]),
    ("Rules", ["rules/", "qt/core_bridge.py"]),
    ("Export", ["export/", "export/targets/"]),
    ("Diagnostics", ["app/safety.py", "diagnostics/", "tools/"]),
    ("Assets / Showcases", ["showcases/", "assets/"]),
]

SKIP_DIRS = {"__pycache__", "user_data", "out", "dist", "build", "venv", ".venv", "node_modules", ".git"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".bin", ".zip", ".pyc", ".pyo"}

def should_skip_path(fp: Path) -> bool:
    # skip hidden files/dirs, caches, build outputs, and binaries
    rel_fp = fp.relative_to(ROOT) if fp.is_absolute() else fp
    for i, part in enumerate(rel_fp.parts):
        if part in SKIP_DIRS:
            return True
        if part.startswith(".") and part not in {".", ".."}:
            # Keep root-level repo control files in the inventory.
            if i == 0 and part in {".gitignore"}:
                continue
            return True
    if fp.suffix.lower() in SKIP_EXTS:
        return True
    return False
def rel(p: Path) -> str:
    return str(p.as_posix())

def list_files_under(prefix: str) -> list[str]:
    p = ROOT / prefix
    out: list[str] = []
    if p.is_file():
        return [rel(p.relative_to(ROOT))]
    if p.is_dir():
        for fp in sorted(p.rglob("*")):
            if not fp.is_file():
                continue
            if should_skip_path(fp):
                continue
            out.append(rel(fp.relative_to(ROOT)))
    return out

def build_index() -> dict:
    idx = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": "/repo/MODULO_LED_STUDIO",
        "categories": [],
    }
    seen = set()
    for title, prefixes in CATEGORIES:
        files = []
        for pref in prefixes:
            for f in list_files_under(pref):
                if f not in seen:
                    files.append(f)
                    seen.add(f)
        idx["categories"].append({"title": title, "files": files})
    # also include a full file list for grep/search tools
    all_files: list[str] = []
    for fp in sorted(ROOT.rglob("*")):
        if not fp.is_file():
            continue
        if should_skip_path(fp):
            continue
        all_files.append(rel(fp.relative_to(ROOT)))
    idx["all_files"] = all_files
    return idx

def write_outputs(idx: dict) -> None:
    _ensure_docs_dir()
    (DOCS / "CODEMAP.json").write_text(json.dumps(idx, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Modulo CODEMAP (code-derived index)")
    lines.append("")
    lines.append(f"Generated: `{idx['generated_utc']}`")
    lines.append("")
    lines.append("This document is an **index into the repository** (where systems live).")
    lines.append("It does **not** claim that every listed system is complete or export-parity-safe.")
    lines.append("")
    for cat in idx["categories"]:
        lines.append(f"## {cat['title']}")
        if not cat["files"]:
            lines.append("_No files matched._")
            lines.append("")
            continue
        for f in cat["files"]:
            lines.append(f"- `{f}`")
        lines.append("")
    lines.append("## Full file list")
    lines.append("See `docs/CODEMAP.json` (`all_files`).")
    lines.append("")
    (DOCS / "CODEMAP.md").write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    idx = build_index()
    write_outputs(idx)
    print("[CODEMAP] Wrote docs/CODEMAP.md and docs/CODEMAP.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())