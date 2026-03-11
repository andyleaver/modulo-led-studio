from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_register_golden_fixture_uses_project_fixtures_dir() -> None:
    text = (ROOT / 'tools' / 'register_golden_fixture.py').read_text(encoding='utf-8')
    assert 'fixtures/projects' in text
    assert 'repo_root / "demos"' not in text
    assert 'Create demos/' not in text


def test_validate_behaviors_uses_project_fixtures_dir() -> None:
    text = (ROOT / 'tools' / 'validate_behaviors.py').read_text(encoding='utf-8')
    assert 'FIXTURE_DIR = ROOT / "fixtures" / "projects"' in text
    assert 'missing fixtures/projects/' in text
    assert 'ROOT / "demos"' not in text
    assert 'missing demos/' not in text
