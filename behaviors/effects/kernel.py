from __future__ import annotations

from core.surface_compat import canonical_surface_config
SHIPPED = True

"""kernel: first-class programmable kernel layer.

Canonical key: 'kernel'

Policy:
- One path only. No legacy runtime aliases.
- Older projects that used behavior 'write_the_loop' are migrated to 'kernel'
  by app/kernel_layers.py during project normalization.

Preview:
- Uses runtime.kernel_runtime (Python kernel runtime) reading params['py'].

Export:
- Exporters inject params['cpp'] (C++ body) for kernel layers.
  This BehaviorDef's arduino_emit is intentionally minimal; exporters own
  generation to keep a single authoritative path.
"""

from typing import List, Tuple, Dict, Any

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

# Preview runtime
from runtime.kernel_runtime import KernelRuntime
from runtime.kernel_status import KernelStatus

# Shared singleton (per-process)
_KERNEL_RT = KernelRuntime()

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, dt: float = 1.0/60.0, frame: int = 0, surface: dict | None = None, layout: dict | None = None, audio: dict | None = None) -> List[RGB]:
    """Preview kernel render.

    PreviewEngine may call preview_emit with extra kwargs; we accept a superset.
    Canonical runtime surface truth is passed on ``surface``.
    ``layout`` is accepted only to support callers that have not been updated yet.
    State is a per-layer dict provided by PreviewEngine.
    """
    n = max(1, int(num_leds))
    st: Dict[str, Any] = state if isinstance(state, dict) else {}
    p = params if isinstance(params, dict) else {}

    # status lives in state to persist across frames
    status = st.get('_kernel_status')
    if not isinstance(status, KernelStatus):
        status = KernelStatus()
        st['_kernel_status'] = status

    src = str(p.get('py') or '')
    runtime_surface = surface if isinstance(surface, dict) else (layout if isinstance(layout, dict) else None)

    return _KERNEL_RT.run_preview(
        num_leds=n,
        surface=runtime_surface,
        params=p,
        t=float(t or 0.0),
        dt=float(dt or 0.0),
        frame=int(frame or 0),
        state=st,
        audio=audio if isinstance(audio, dict) else None,
        status=status,
        source=src,
    )

def _arduino_emit(*, surface: dict | None = None, layout: dict | None = None, params: dict) -> str:
    surface = surface if surface is not None else layout
    surface_cfg = canonical_surface_config(surface)
    """Exporter-owned.

    Keeping this minimal avoids a second competing code path.
    """
    return "// kernel: exporter-owned (params['cpp'] injected by exporter)\n"

def register_kernel():
    return register(BehaviorDef(
        'kernel',
        title='Kernel',
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
        uses=['kernel', 'no_ceiling'],
    ))
