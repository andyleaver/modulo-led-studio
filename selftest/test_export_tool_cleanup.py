from __future__ import annotations

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


def test_target_registry_validation_is_clean() -> None:
    from export.targets.registry import validate_targets

    assert validate_targets() == []


def test_parity_sweep_writes_to_artifacts_not_repo() -> None:
    repo_parity = ROOT / 'parity_reports'
    if repo_parity.exists():
        shutil.rmtree(repo_parity)

    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'parity_sweep.py'), '--json-summary'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not repo_parity.exists(), 'parity_sweep should not recreate repo parity_reports/'
    assert str((ROOT.parent / 'artifacts' / 'parity_reports')) in proc.stdout


def test_golden_exports_accepts_out_dir_arg() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'golden_exports.py'), '--help'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '--out-dir' in proc.stdout

def test_golden_exports_runs_real_fixture_set() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'golden_exports.py')],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'Golden exports OK (4 fixtures).' in proc.stdout


def test_compile_sanity_uses_real_targets_and_exportable_behaviors() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'compile_sanity.py')],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    summary_path = None
    for line in (proc.stdout or '').splitlines():
        if line.startswith('Wrote: '):
            summary_path = Path(line.split('Wrote: ', 1)[1].strip())
            break
    assert summary_path is not None and summary_path.exists(), proc.stdout + proc.stderr

    import json
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    runs = summary.get('runs') or []
    assert runs, summary
    bad = [r for r in runs if str(r.get('status')) in {'ERR', 'SKIP'}]
    assert bad == [], bad
    targets = {str(r.get('target')) for r in runs}
    behaviors = {str(r.get('behavior')) for r in runs}
    assert 'arduino_avr_fastled_noaudio' in targets
    assert {'solid', 'rainbow', 'chase'}.issubset(behaviors)
