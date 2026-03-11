from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_codemap_inventory_includes_repo_control_and_generated_docs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["cp", "-R", str(ROOT), str(repo)], check=True)
    subprocess.run([sys.executable, str(repo / "tools" / "codemap_audit.py")], cwd=repo, check=True)
    data = json.loads((repo / "docs" / "CODEMAP.json").read_text(encoding="utf-8"))
    all_files = set(data.get("all_files", []))
    assert ".gitignore" in all_files
    assert "CHANGELOG.md" in all_files
    assert "docs/CODEMAP.json" in all_files
    assert "docs/CODEMAP.md" in all_files
