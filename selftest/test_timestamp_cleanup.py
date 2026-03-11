from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_deprecated_utcnow_in_cleaned_modules() -> None:
    paths = [
        ROOT / 'tools' / 'compile_sanity.py',
        ROOT / 'app' / 'safety.py',
        ROOT / 'app' / 'effect_audit.py',
        ROOT / 'app' / 'project_diagnostics_health.py',
        ROOT / 'qt' / 'diagnostics_console_full_audit_probes.py',
    ]
    for path in paths:
        text = path.read_text(encoding='utf-8')
        assert 'utcnow(' not in text, path.name
