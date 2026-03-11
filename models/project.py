from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# diagnostics (no silent failure)
def _proj_diag_exc(e: BaseException, code: str, summary: str, details: dict | None = None) -> None:
    try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.exception(e, domain='PROJECT', code=code, summary=summary, details=details or {})
    except Exception:
        return

@dataclass
class Layout:
    # Canonical layout model (single truth):
    # - shape: 'strip' or 'cells'
    # - strip: count
    # - cells: width/height/cell_size + count
    shape: str = "strip"

    # Clean boot default (per policy): strip with 144 LEDs.
    count: int = 144

    # Cells canonical fields
    width: int = 16
    height: int = 16
    cell_size: int = 20

    # Mapping options (preview + export parity)
    serpentine: bool = False
    flip_x: bool = False
    flip_y: bool = False
    rotate: int = 0

    def __post_init__(self):
        try:
            self.count = int(self.count)
            self.width = int(self.width)
            self.height = int(self.height)
            self.cell_size = int(self.cell_size)
        except Exception as e:
            _proj_diag_exc(e, code='LAYOUT_POST_INIT_FAIL', summary='Failed normalizing layout fields', details={
                'count': getattr(self, 'count', None),
                'width': getattr(self, 'width', None),
                'height': getattr(self, 'height', None),
                'cell_size': getattr(self, 'cell_size', None),
            })

def _plainify(obj: Any) -> Any:
    """Recursively convert model objects into JSON-safe plain containers."""
    try:
        if isinstance(obj, dict):
            return {k: _plainify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_plainify(v) for v in obj]
        if isinstance(obj, tuple):
            return [_plainify(v) for v in obj]
        if hasattr(obj, '__dict__') and not isinstance(obj, type):
            return {k: _plainify(v) for k, v in vars(obj).items() if not str(k).startswith('_')}
    except Exception as e:
        _proj_diag_exc(e, code='PROJECT_PLAINIFY_FAIL', summary='Failed plainifying project model object')
    return obj

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
    kind: str = "effect"  # effect|kernel
    behavior: str = "solid"
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: str = "over"  # over|add|max|multiply|screen
    order: int = 0
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
    surface: Layout = field(default_factory=Layout)
    # Clean boot default (per policy): zero layers.
    layers: List[Layer] = field(default_factory=list)
    export_audio: dict = None  # {'use_spectrum_shield':bool,'reset_pin':int,'strobe_pin':int,'left_pin':str,'right_pin':str}
    preview_audio: dict = None  # {'mode':str,'port':str,'baud':int,'gain':float,'smoothing':float,'meter':str,'autoconnect':bool}
    postfx: dict = None  # {'bleed_amount':float,'bleed_radius':int,'trail_amount':float}
    ui: Dict[str, Any] = field(default_factory=dict)
    audio: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=lambda: {'number': {}, 'toggle': {}})
    masks: Dict[str, Any] = field(default_factory=dict)

    # Project-level Rules (Phase 2 Authoring: Rules MVP)
    # Stored as a list of dicts so the schema can evolve without breaking old files.
    rules: List[dict] = field(default_factory=list)

    groups: List[PixelGroup] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize canonical UI selection state for model instances.

        The authoritative selection field is ``ui.selected_layer``. Legacy top-level
        ``active_layer`` is no longer stored on the model as live runtime truth.
        """
        layers = self.layers if isinstance(self.layers, list) else []
        ui = self.ui if isinstance(self.ui, dict) else {}
        ui = dict(ui)
        try:
            selected = int(ui.get('selected_layer', -1))
        except Exception:
            selected = -1
        if not layers:
            selected = -1
        else:
            if selected < 0:
                selected = 0
            if selected >= len(layers):
                selected = len(layers) - 1
        ui['selected_layer'] = int(selected)
        self.ui = ui

    @property
    def layout(self) -> Layout:
        """Compatibility alias for older code crossing the final surface seam.

        Canonical model surface truth now lives on ``project.surface``.
        ``project.surface`` is the live model field; ``project.layout`` remains a compatibility alias only.
        """
        return self.surface

    @layout.setter
    def layout(self, value: Layout) -> None:
        self.surface = value

    def to_dict(self) -> Dict[str, Any]:
        """Return canonical project dict for app/runtime use.

        Canonical exported project dictionaries must use ``ui.selected_layer``.
        Legacy top-level ``active_layer`` is migration-only and is not emitted.
        """
        try:
            data = _plainify(asdict(self))
            data.pop('active_layer', None)
            layers = data.get('layers') or []
            if not isinstance(layers, list):
                layers = []
                data['layers'] = layers
            ui = data.get('ui') if isinstance(data.get('ui'), dict) else {}
            ui = dict(ui)
            if 'selected_layer' in ui:
                try:
                    selected = int(ui.get('selected_layer', -1))
                except Exception:
                    selected = -1 if not layers else 0
            else:
                selected = -1 if not layers else 0
            if not layers:
                selected = -1
            else:
                if selected < 0:
                    selected = 0
                if selected >= len(layers):
                    selected = len(layers) - 1
            ui['selected_layer'] = int(selected)
            data['ui'] = ui
            surface = data.get('surface') if isinstance(data.get('surface'), dict) else {}
            surface = dict(surface)
            data['surface'] = surface
            data.pop('layout', None)
            export_cfg = data.get('export') if isinstance(data.get('export'), dict) else {}
            export_cfg = dict(export_cfg)
            export_hw = export_cfg.get('hw') if isinstance(export_cfg.get('hw'), dict) else {}
            export_hw = dict(export_hw)
            export_cfg['hw'] = export_hw
            data['export'] = export_cfg
            audio = data.get('audio') if isinstance(data.get('audio'), dict) else {}
            data['audio'] = dict(audio)
            variables = data.get('variables') if isinstance(data.get('variables'), dict) else {}
            number = variables.get('number') if isinstance(variables.get('number'), dict) else {}
            toggle = variables.get('toggle') if isinstance(variables.get('toggle'), dict) else {}
            data['variables'] = {'number': dict(number), 'toggle': dict(toggle)}
            masks = data.get('masks') if isinstance(data.get('masks'), dict) else {}
            data['masks'] = dict(masks)
            return data
        except Exception as e:
            _proj_diag_exc(e, code='PROJECT_TO_DICT_FAIL', summary='Failed converting Project to canonical dict')
            surface = _plainify(asdict(self.surface))
            if not isinstance(surface, dict):
                surface = {}
            return {
                'surface': surface,
                'layers': [_plainify(asdict(l)) for l in (self.layers or [])],
                'ui': {'selected_layer': (-1 if not (self.layers or []) else 0)},
                'export': {'hw': {}},
                'audio': {},
                'variables': {'number': {}, 'toggle': {}},
                'masks': {},
                'rules': list(self.rules or []),
                'groups': [_plainify(asdict(g)) for g in (self.groups or [])],
                'zones': [_plainify(asdict(z)) for z in (self.zones or [])],
            }
