from __future__ import annotations

# Example mod: registers a life-like CA module (HighLife B36/S23)

from app.mod_api import register_ca_module


def py_step(src, dst, w, h, params):
    B = set([3, 6])
    S = set([2, 3])
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


CPP_STEP = r"""
  // HighLife B36/S23 encoded as bitmasks.
  // params: Bmask/Smask are passed by the exporter; default B=3,6 and S=2,3.
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


register_ca_module(
    name="highlife_B36S23",
    kind="life2d",
    description="HighLife (B36/S23)",
    py_step=py_step,
    cpp_step_body=CPP_STEP,
)
