from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def test_preview_bridge_uses_artifact_temp_dir_not_repo_out() -> None:
    from preview.preview_project_bridge import _preview_temp_dir

    repo_out = ROOT / 'out'
    if repo_out.exists():
        shutil.rmtree(repo_out)

    tmp_dir = _preview_temp_dir(str(ROOT))
    assert tmp_dir is not None
    assert tmp_dir == ROOT.parent / 'artifacts' / 'preview_tmp'
    assert tmp_dir.exists()
    assert not repo_out.exists(), 'preview bridge should not recreate repo out/'


def test_codemap_audit_creates_docs_dir_lazily() -> None:
    docs_dir = ROOT / 'docs'
    if docs_dir.exists():
        shutil.rmtree(docs_dir)

    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'codemap_audit.py')],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (docs_dir / 'CODEMAP.md').exists()
    assert (docs_dir / 'CODEMAP.json').exists()


def test_compile_sanity_help_exposes_out_dir() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'compile_sanity.py'), '--help'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '--out-dir' in proc.stdout
