from __future__ import annotations

from pathlib import Path
from typing import Tuple
import json

from ...ir import ShowIR

def emit(*, ir: ShowIR, out_path: Path, **_kwargs) -> Tuple[Path, str]:
    """Placeholder Teensy target.

    This exists to prove the 'one engine, many targets' path:
    - capability profile is real
    - parity gates can evaluate against this target
    - emitter is intentionally blocked until we implement a real backend
    """
    meta = {}
    try:
        meta = json.loads((Path(__file__).resolve().parent / "target.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    raise RuntimeError(
        "Target 'teensy41_fastled' is a placeholder pack: gating works, but emitting is not implemented yet. "
        "Choose 'arduino_avr_fastled_msgeq7' for real exports."
    )
