from __future__ import annotations
"""Headless preview runner for regression tests."""

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from models.io import load_project
from preview.audio_input import AudioInput
from preview.preview_engine import PreviewEngine
from preview.preview_project_bridge import prepare_preview_project


def _buf_to_bytes(buf) -> bytes:
    out = bytearray()
    if not buf:
        return bytes(out)
    v0 = buf[0]
    if isinstance(v0, int):
        for x in buf:
            out.extend(int(x).to_bytes(4, "little", signed=False))
    else:
        for r, g, b in buf:
            out.append(int(r) & 0xFF)
            out.append(int(g) & 0xFF)
            out.append(int(b) & 0xFF)
    return bytes(out)


def run_headless(project_path: Path, fixture_path: Path, frames: int = 60, fps: float = 30.0) -> str:
    project = load_project(Path(project_path))
    try:
        project_model, _issues, _clean = prepare_preview_project(project, root_dir=None)
    except Exception:
        project_model = project

    audio = AudioInput()
    audio.recorder.load(Path(fixture_path))
    audio.recorder.start_play(0.0)
    audio.mode = "playback"
    audio.gain = 1.0
    audio.smoothing = 0.0

    eng = PreviewEngine(project=project_model, audio=audio, fixed_dt=1.0 / 60.0)
    dt = 1.0 / max(1.0, float(fps))
    h = hashlib.sha256()

    t = 0.0
    for _ in range(int(frames)):
        audio.step(t)
        buf = eng.render_frame(t)
        h.update(_buf_to_bytes(buf))
        t += dt

    return h.hexdigest()


@dataclass
class HeadlessResult:
    sha256: str
    frames: int
    fps: float


def run_and_write(project_path: Path, fixture_path: Path, out_json: Path, frames: int = 60, fps: float = 30.0) -> HeadlessResult:
    sha = run_headless(project_path, fixture_path, frames=frames, fps=fps)
    res = HeadlessResult(sha256=sha, frames=int(frames), fps=float(fps))
    Path(out_json).write_text(json.dumps(res.__dict__, indent=2), encoding="utf-8")
    return res
