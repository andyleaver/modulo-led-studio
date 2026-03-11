from __future__ import annotations
from typing import Tuple

import behaviors  # noqa: F401

from preview.preview_engine_support import (
    _PROJECT_POSTFX_CACHE,
    _postfx_project_key,
)
from preview.preview_engine_blend import PreviewEngineBlendMixin
from preview.preview_engine_render import PreviewEngineRenderMixin

RGB = Tuple[int, int, int]


class PreviewEngine(PreviewEngineRenderMixin, PreviewEngineBlendMixin):
    """Canonical preview engine used by Qt, diagnostics, and headless preview.

    The engine consumes canonical project surface and layer fields only, so every
    caller sees the same preview truth.
    """

    def __init__(self, project=None, audio=None, fixed_dt: float = 1.0 / 60.0, signal_bus=None, **kwargs):
        self.project = project or {}
        self.project_data = self.project
        self.audio = audio
        self.signal_bus = signal_bus
        self._extra_init_kwargs = dict(kwargs or {})
        self.fixed_dt = float(fixed_dt or (1.0 / 60.0))
        self._last_frame = []
        self.last_error = None
        self.last_traceback = None
        self._state_by_uid = {}
        self._mask_indices = None
        self.target_mask = None
        self._last_render_stats = {}
        self._last_layers_signature = {'enabled_n': 0, 'layers': []}
        self._last_live_rows = []
        self._last_layer_stats = {}
        self._debug_last_trace = []
        self._rt_layer_fields = []
        self._state_map = {}
        self.fps = 0.0
        self._fps_last_t = 0.0
        self._fps_frames = 0
