from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_qt_cleanup_modules_use_qt_compat() -> None:
    targets = [
        ROOT / 'qt' / 'wiretap.py',
        ROOT / 'qt' / 'wiretap_manager.py',
        ROOT / 'qt' / 'wiretap_overlay.py',
        ROOT / 'qt' / 'wiretap_support.py',
        ROOT / 'qt' / 'layout_panel.py',
        ROOT / 'qt' / 'layout_panel_common.py',
        ROOT / 'qt' / 'era_panel_progress.py',
        ROOT / 'qt' / 'era_panel_text.py',
    ]
    for path in targets:
        text = path.read_text(encoding='utf-8')
        assert ('qt.qt_compat' in text) or ('qt.layout_panel_common' in text), path.name
        assert 'from PySide6' not in text, path.name
        assert 'from PyQt6' not in text, path.name
        assert 'import PySide6' not in text, path.name
        assert 'import PyQt6' not in text, path.name
