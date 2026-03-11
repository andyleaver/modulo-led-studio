from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def test_package_release_creates_clean_artifact() -> None:
    artifact_dir = ROOT.parent / 'artifacts' / 'package_release_test'
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'package_release.py'), '--out-dir', str(artifact_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    zip_paths = sorted(artifact_dir.glob('Modulo_Release_*.zip'))
    assert zip_paths, 'package_release should create a zip artifact'
    zpath = zip_paths[-1]
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
        assert names, 'zip should not be empty'
        top = {name.split('/', 1)[0] for name in names if '/' in name}
        assert top == {ROOT.name}, top
        assert not any('__pycache__/' in name for name in names)
        assert not any(name.endswith('.pyc') or name.endswith('.pyo') for name in names)
        assert not any(name.startswith(f'{ROOT.name}/dist/') for name in names)
        assert not any(name.startswith(f'{ROOT.name}/parity_reports/') for name in names)
