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


def test_repo_hygiene_passes(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc', '*.pyo', 'artifacts'),
    )
    proc = subprocess.run([sys.executable, 'tools/repo_hygiene.py'], cwd=repo, capture_output=True, text=True, timeout=30, env=_clean_env())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'REPO HYGIENE OK' in proc.stdout


def test_repo_hygiene_rejects_recursive_junk(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'tools').mkdir()
    (repo / 'tools' / 'repo_hygiene.py').write_text((ROOT / 'tools' / 'repo_hygiene.py').read_text(encoding='utf-8'), encoding='utf-8')
    bad_dir = repo / 'app' / '__pycache__'
    bad_dir.mkdir(parents=True)
    (bad_dir / 'x.pyc').write_bytes(b'00')

    proc = subprocess.run([sys.executable, 'tools/repo_hygiene.py'], cwd=repo, capture_output=True, text=True, timeout=30, env=_clean_env())
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert '__pycache__' in proc.stdout
    assert '.pyc' in proc.stdout


def test_repo_hygiene_rejects_step_release_note_files(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'tools').mkdir()
    (repo / 'tools' / 'repo_hygiene.py').write_text((ROOT / 'tools' / 'repo_hygiene.py').read_text(encoding='utf-8'), encoding='utf-8')
    (repo / 'RELEASE_NOTES_STEP999.txt').write_text('scratch notes', encoding='utf-8')

    proc = subprocess.run([sys.executable, 'tools/repo_hygiene.py'], cwd=repo, capture_output=True, text=True, timeout=30, env=_clean_env())
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert 'RELEASE_NOTES_STEP999.txt' in proc.stdout


def test_repo_hygiene_rejects_build_history_text(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'tools').mkdir()
    (repo / 'tools' / 'repo_hygiene.py').write_text((ROOT / 'tools' / 'repo_hygiene.py').read_text(encoding='utf-8'), encoding='utf-8')
    (repo / 'notes.txt').write_text('MODULO_LED_STUDIO_PROPER_REFACTOR_STEP260', encoding='utf-8')

    proc = subprocess.run([sys.executable, 'tools/repo_hygiene.py'], cwd=repo, capture_output=True, text=True, timeout=30, env=_clean_env())
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert 'build-history text' in proc.stdout


def test_repo_hygiene_rejects_junk_named_top_level_docs(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'tools').mkdir()
    (repo / 'tools' / 'repo_hygiene.py').write_text((ROOT / 'tools' / 'repo_hygiene.py').read_text(encoding='utf-8'), encoding='utf-8')
    (repo / 'FINAL_UI_POLISH_NOTES.txt').write_text('notes', encoding='utf-8')

    proc = subprocess.run([sys.executable, 'tools/repo_hygiene.py'], cwd=repo, capture_output=True, text=True, timeout=30, env=_clean_env())
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert 'FINAL_UI_POLISH_NOTES.txt' in proc.stdout
