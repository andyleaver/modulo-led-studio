from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_headless_fixture_runner_returns_hash() -> None:
    from preview.headless import run_headless

    sha = run_headless(
        ROOT / 'fixtures' / 'projects' / 'order_pipeline_lock.json',
        ROOT / 'fixtures' / 'demo_audio_1s.jsonl',
        frames=2,
        fps=30.0,
    )
    assert isinstance(sha, str)
    assert len(sha) == 64


def test_resolver_reads_model_backed_surface_mapping() -> None:
    from models.io import load_project
    from runtime.resolver import get_address

    project = load_project(ROOT / 'fixtures' / 'projects' / 'order_pipeline_lock_matrix8x8_mapstress.json')
    assert get_address(project, 'project.surface.width', default=None) == 8
    assert get_address(project, 'project.surface.height', default=None) == 8
