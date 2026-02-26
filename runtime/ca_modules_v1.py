"""CA Modules V1

This is the "custom CA rule modules" escape hatch.

Design goals:
- Let coders register new CA update rules at runtime (preview + export).
- Keep the core engine deterministic.
- Avoid duplicating existing CA cluster code: we reuse the same CA buffers in preview and in export.

Security note:
Export embeds C++ snippets provided by modules. This is an advanced extension point.
Sandboxing/versioning is handled at the mod-loader policy layer (Phase 3 later).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from runtime.extensions_v1 import register_health_probe


PyStepFn = Callable[[List[int], List[int], int, int, Dict], None]


@dataclass(frozen=True)
class CAModuleV1:
    """A cellular-automaton module.

    kind:
      - "life2d": 2D life-like CA on matrix
      - "elem1d": 1D elementary CA on strip

    The module must provide BOTH:
      - py_step: used for preview
      - cpp_step: injected into Arduino export
    """

    name: str
    kind: str
    description: str

    # Preview step (writes next into dst, reads src)
    py_step: PyStepFn

    # Export step: C++ snippet inserted as the body of:
    #   static inline void ca_module_step_<safe_name>(...)
    # The signature is fixed by the exporter.
    cpp_step_body: str


_REGISTRY: Dict[str, CAModuleV1] = {}


def list_ca_modules() -> List[str]:
    return sorted(_REGISTRY.keys())


def get_ca_module(name: str) -> Optional[CAModuleV1]:
    return _REGISTRY.get(name)


def register_ca_module(module: CAModuleV1) -> None:
    if not module.name or not isinstance(module.name, str):
        raise ValueError("CAModuleV1.name must be a non-empty string")
    if module.kind not in ("life2d", "elem1d"):
        raise ValueError(f"CAModuleV1.kind must be 'life2d' or 'elem1d' (got {module.kind!r})")
    _REGISTRY[module.name] = module


# -----------------------
# Built-in modules (examples + usable defaults)
# -----------------------


def _py_step_life_like(src: List[int], dst: List[int], w: int, h: int, params: Dict) -> None:
    # params expects: B (list[int]), S (list[int])
    B = set(int(x) for x in params.get("B", [3]))
    S = set(int(x) for x in params.get("S", [2, 3]))
    n = min(len(src), w * h)
    for i in range(n):
        x = i % w
        y = i // w
        alive = 1 if src[i] else 0
        nb = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                xx = x + dx
                yy = y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    nb += 1 if src[yy * w + xx] else 0
        if alive:
            dst[i] = 1 if nb in S else 0
        else:
            dst[i] = 1 if nb in B else 0


_CPP_STEP_LIFE_LIKE = r"""
  // params: Bmask (birth bits 0..8), Smask (survive bits 0..8)
  // src/dst are flattened mw*mh arrays, values 0/1
  int n = mw*mh;
  if(n > num_leds) n = num_leds;
  for(int i=0;i<n;i++){
    int x = i % mw;
    int y = i / mw;
    uint8_t alive = src[i] ? 1 : 0;
    int nb = 0;
    for(int dy=-1; dy<=1; dy++){
      for(int dx=-1; dx<=1; dx++){
        if(dx==0 && dy==0) continue;
        int xx = x + dx;
        int yy = y + dy;
        if(xx>=0 && xx<mw && yy>=0 && yy<mh){
          nb += src[yy*mw + xx] ? 1 : 0;
        }
      }
    }
    uint32_t bit = (1u << (uint32_t)nb);
    if(alive){
      dst[i] = (Smask & bit) ? 1 : 0;
    } else {
      dst[i] = (Bmask & bit) ? 1 : 0;
    }
  }
"""


def _py_step_elem_rule(src: List[int], dst: List[int], w: int, h: int, params: Dict) -> None:
    # 1D elementary rule on strip. w is num_leds.
    rule = int(params.get("rule", 30)) & 0xFF
    n = min(len(src), w)
    for i in range(n):
        l = src[i - 1] if i - 1 >= 0 else 0
        c = src[i]
        r = src[i + 1] if i + 1 < n else 0
        idx = (l << 2) | (c << 1) | r
        dst[i] = 1 if ((rule >> idx) & 1) else 0


_CPP_STEP_ELEM_RULE = r"""
  // params: rule8 (0..255)
  int n = num_leds;
  for(int i=0;i<n;i++){
    uint8_t l = (i>0) ? (src[i-1]?1:0) : 0;
    uint8_t c = src[i]?1:0;
    uint8_t r = (i+1<n) ? (src[i+1]?1:0) : 0;
    uint8_t idx = (l<<2) | (c<<1) | r;
    dst[i] = ((rule8 >> idx) & 1u) ? 1 : 0;
  }
"""


# Register a couple of useful built-ins.
register_ca_module(
    CAModuleV1(
        name="life_B3S23",
        kind="life2d",
        description="Conway's Game of Life (B3/S23)",
        py_step=_py_step_life_like,
        cpp_step_body=_CPP_STEP_LIFE_LIKE,
    )
)

register_ca_module(
    CAModuleV1(
        name="elem_rule30",
        kind="elem1d",
        description="Elementary CA Rule 30 (1D strip)",
        py_step=_py_step_elem_rule,
        cpp_step_body=_CPP_STEP_ELEM_RULE,
    )
)


def _health_probe_ca_modules():
    return {
        "count": len(_REGISTRY),
        "modules": list_ca_modules(),
    }


register_health_probe("ca_modules", _health_probe_ca_modules)
