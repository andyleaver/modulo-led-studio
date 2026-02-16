from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Layout:
    shape: str = "strip"   # 'strip' or 'cells'
    num_leds: int = 60
    led_pin: int = 6
    # --- Matrix / cells layout fields ---
    # Different parts of the codebase historically used different key names.
    # We keep BOTH sets so:
    #   - Qt/UI (project dict) can use matrix_w/matrix_h/cell_size
    #   - PreviewEngine can use mw/mh/cell (older internal naming)
    #
    # NOTE: These are kept in sync in __post_init__ and by the Qt setters.
    matrix_w: int = 16
    matrix_h: int = 16
    cell_size: int = 20
    mw: int = 16
    mh: int = 16
    cell: int = 20
    # --- Matrix wiring / mapping options (preview + export parity) ---
    serpentine: bool = True
    flip_x: bool = False
    flip_y: bool = False
    rotate: int = 0  # 0/90/180/270

    def __post_init__(self):
        # If one naming style was provided, mirror it into the other.
        try:
            if int(self.mw) == 16 and int(self.matrix_w) != 16:
                self.mw = int(self.matrix_w)
            if int(self.mh) == 16 and int(self.matrix_h) != 16:
                self.mh = int(self.matrix_h)
            if int(self.cell) == 20 and int(self.cell_size) != 20:
                self.cell = int(self.cell_size)
            # Mirror back the other way too (in case mw/mh/cell were set).
            if int(self.matrix_w) == 16 and int(self.mw) != 16:
                self.matrix_w = int(self.mw)
            if int(self.matrix_h) == 16 and int(self.mh) != 16:
                self.matrix_h = int(self.mh)
            if int(self.cell_size) == 20 and int(self.cell) != 20:
                self.cell_size = int(self.cell)
        except Exception:
            pass

@dataclass
class ModulotorSpec:
    enabled: bool = False
    target: str = "brightness"
    source: str = "lfo_sine"
    mode: str = "mul"
    amount: float = 0.5
    rate_hz: float = 0.5
    bias: float = 0.0
    smooth: float = 0.0

@dataclass
class Layer:
    uid: str = ""
    name: str = "Layer 1"
    behavior: str = "solid"
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "over"  # over|add|max|multiply|screen
    target_kind: str = "all"  # all|group|zone
    target_ref: int = 0       # index into Project.groups or Project.zones

    # Per-effect Variables (): user-defined state values owned by this effect.
    # Stored in the project so they can be used by Rules and exported later.
    variables: List[Dict[str, Any]] = field(default_factory=list)

    # Per-effect Rules (): simple condition -> action rules that operate on variables.
    rules: List[Dict[str, Any]] = field(default_factory=list)

    # Operators/PostFX MVP: per-layer operators (preview-only until runtime support exists)
    operators: List[Dict[str, Any]] = field(default_factory=list)


    params: Dict[str, Any] = field(default_factory=lambda: {
        "color": (255, 0, 0),
        "brightness": 1.0,
        "speed": 1.0,
        "width": 0.2,
        "softness": 0.0,
        "direction": 1.0,
        "density": 0.5,
        "purpose_f0": 0.0,
        "purpose_f1": 0.0,
        "purpose_f2": 0.0,
        "purpose_f3": 0.0,
        "purpose_i0": 0,
        "purpose_i1": 0,
        "purpose_i2": 0,
        "purpose_i3": 0,

    })

    modulotors: List[ModulotorSpec] = field(default_factory=lambda: [ModulotorSpec(), ModulotorSpec(), ModulotorSpec()])


@dataclass
class PixelGroup:
    name: str = "Group 1"
    # indices into the flattened LED list (strip or matrix cells)
    indices: List[int] = field(default_factory=list)

@dataclass
class Zone:
    name: str = "Zone 1"
    # For strips: inclusive start/end indices. For cells: can be used as a range on flattened indices too.
    start: int = 0
    end: int = 0


@dataclass
class Project:
    layout: Layout = field(default_factory=Layout)
    layers: List[Layer] = field(default_factory=lambda: [Layer()])
    export_audio: dict = None  # {'use_spectrum_shield':bool,'reset_pin':int,'strobe_pin':int,'left_pin':str,'right_pin':str}
    preview_audio: dict = None  # {'mode':str,'port':str,'baud':int,'gain':float,'smoothing':float,'meter':str,'autoconnect':bool}
    postfx: dict = None  # {'bleed_amount':float,'bleed_radius':int,'trail_amount':float}
    active_layer: int = 0

    # Project-level Rules (Phase 2 Authoring: Rules MVP)
    # Stored as a list of dicts so the schema can evolve without breaking old files.
    rules: List[dict] = field(default_factory=list)

    groups: List[PixelGroup] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)