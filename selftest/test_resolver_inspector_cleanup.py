from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_resolver_inspector_uses_artifacts_and_real_fixture() -> None:
    tool = ROOT / "tools" / "resolver_inspector.py"
    text = tool.read_text(encoding="utf-8")
    assert 'app" / "showcases" / "demo_project.json"' not in text
    assert 'repo_root / "resolver_inspector.json"' not in text
    assert 'fixtures" / "projects" / "order_pipeline_lock.json"' in text

    repo_report = ROOT / "resolver_inspector.json"
    if repo_report.exists():
        repo_report.unlink()

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert not repo_report.exists(), "resolver_inspector should not write into the repo root"
    expected = ROOT.parent / "artifacts" / "resolver_inspector" / "resolver_inspector.json"
    assert expected.exists(), proc.stdout
    assert str(expected) in proc.stdout



def test_shadow_keys_uses_fixture_fallback() -> None:
    text = (ROOT / "selftest" / "test_shadow_keys.py").read_text(encoding="utf-8")
    assert "app/showcases/demo_project.json" not in text
    assert "order_pipeline_lock.json" in text
    assert "fixtures" in text
