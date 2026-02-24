from __future__ import annotations
from pathlib import Path
from typing import Tuple
from ...ir import ShowIR
from ..arduino_avr_fastled_msgeq7.emitter import emit as _emit

def emit(*, ir: ShowIR, out_path: Path, **kwargs) -> Tuple[Path, str]:
    return _emit(ir=ir, out_path=out_path, **kwargs)
