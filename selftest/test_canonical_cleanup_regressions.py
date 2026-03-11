from __future__ import annotations

from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_behavior_template_uses_canonical_factory() -> None:
    module = _load_module(ROOT / 'templates' / 'behavior_effect_template.py', 'behavior_template_test')
    assert hasattr(module, 'build_behavior_def')
    behavior_def = module.build_behavior_def()
    assert behavior_def.key == module.BEHAVIOR_ID
    assert callable(module.preview_emit)
    assert callable(module.arduino_emit)


def test_repo_hygiene_tool_passes(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc', '*.pyo', 'artifacts'),
    )
    proc = subprocess.run(
        [sys.executable, str(repo / 'tools' / 'repo_hygiene.py')],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=_clean_env(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_qt_modules_use_qt_compat() -> None:
    targets = [
        ROOT / 'qt' / 'era_panel.py',
        ROOT / 'qt' / 'era_panel_ui.py',
        ROOT / 'qt' / 'layers_panel_ui.py',
        ROOT / 'qt' / 'era_panel_workbench.py',
    ]
    for path in targets:
        text = path.read_text(encoding='utf-8')
        assert 'qt.qt_compat' in text
        assert 'PySide6' not in text
        assert 'PyQt6' not in text
