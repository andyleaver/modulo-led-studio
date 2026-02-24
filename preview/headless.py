from __future__ import annotations
"""Headless preview runner for regression tests.

It runs the preview engine without any Tkinter, producing a stable hash of the LED buffer
for a given project + audio input fixture.

This is the foundation for 'I don't have to manually test every step'.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import hashlib
import json
import time

from models.io import load_project
from preview.audio_input import AudioInput

# Engine is expected to exist in preview/engine.py with a PreviewEngine(project, audio_input)
# and .render_frame(t)-> list[(r,g,b)] or list[int] (0xRRGGBB) depending on implementation.
# We provide a thin adapter that works with either.
from preview.preview_engine import PreviewEngine  # type: ignore


def _buf_to_bytes(buf) -> bytes:
    # buf may be list of tuples or list of ints
    out = bytearray()
    if not buf:
        return bytes(out)
    v0 = buf[0]
    if isinstance(v0, int):
        for x in buf:
            out.extend(int(x).to_bytes(4, "little", signed=False))
    else:
        # assume tuple/list length 3
        for r,g,b in buf:
            out.append(int(r) & 0xFF)
            out.append(int(g) & 0xFF)
            out.append(int(b) & 0xFF)
    return bytes(out)


def run_headless(project_path: Path, fixture_path: Path, frames: int = 60, fps: float = 30.0) -> str:
    project = load_project(Path(project_path))
    audio = AudioInput()
    audio.recorder.load(Path(fixture_path))
    audio.recorder.start_play(0.0)
    audio.mode = "playback"
    audio.gain = 1.0
    audio.smoothing = 0.0

    eng = PreviewEngine(project=project, audio=audio, fixed_dt=1.0/60.0)
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
