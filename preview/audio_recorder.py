from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import time

@dataclass
class RecordedFrame:
    t: float
    state: Dict[str, float]

class AudioRecorder:
    """Record and playback audio states (energy/mono/l/r) for deterministic preview.

    Storage format: JSON Lines (.jsonl)
      {"t":0.000,"state":{"energy":0.1,"mono0":...}}
    """

    def __init__(self):
        self.recording: bool = False
        self.frames: List[RecordedFrame] = []
        self._t0: float = 0.0

        self.playing: bool = False
        self._play_start_wall: float = 0.0
        self._play_start_t: float = 0.0
        self._play_idx: int = 0

    def start_record(self):
        self.frames.clear()
        self.recording = True
        self._t0 = time.time()

    def stop_record(self):
        self.recording = False

    def add_frame(self, state: Dict[str, float]):
        if not self.recording:
            return
        t = time.time() - self._t0
        self.frames.append(RecordedFrame(t=t, state=dict(state)))

    def save(self, path: Path):
        path = Path(path)
        lines = []
        for f in self.frames:
            lines.append(json.dumps({"t": float(f.t), "state": dict(f.state)}, separators=(",",":")))
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def load(self, path: Path):
        path = Path(path)
        self.frames.clear()
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                t = float(obj.get("t", 0.0))
                st = obj.get("state", {})
                if isinstance(st, dict):
                    self.frames.append(RecordedFrame(t=t, state={str(k): float(v) for k,v in st.items() if _is_number(v)}))
            except Exception:
                continue
        # ensure sorted by t
        self.frames.sort(key=lambda f: f.t)

    def start_play(self, start_t: float = 0.0):
        self.playing = True
        self._play_start_wall = time.time()
        self._play_start_t = float(start_t)
        self._play_idx = 0
        # advance to start_t
        while self._play_idx < len(self.frames) and self.frames[self._play_idx].t < self._play_start_t:
            self._play_idx += 1

    def stop_play(self):
        self.playing = False

    def sample(self) -> Optional[Dict[str, float]]:
        """Return the state for current playback time, or None if not playing/finished."""
        if not self.playing or not self.frames:
            return None
        t_now = (time.time() - self._play_start_wall) + self._play_start_t
        # move forward until next frame time
        while self._play_idx + 1 < len(self.frames) and self.frames[self._play_idx + 1].t <= t_now:
            self._play_idx += 1
        if self._play_idx >= len(self.frames):
            self.playing = False
            return None
        return dict(self.frames[self._play_idx].state)

def _is_number(x) -> bool:
    try:
        float(x)
        return True
    except Exception:
        return False
