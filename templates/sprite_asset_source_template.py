"""Sprite asset *source* template.

Keep this file human-editable. It is allowed to be verbose.
If/when memory becomes tight on AVR-class boards, generate a packed version
(palette + RLE) alongside it, and switch the behavior to import that.

Rules:
- Provide ASSETS dict with entries {w,h,pix}.
- pix must be flat list length w*h.
- Use SKY for transparency key (optional).
"""

from __future__ import annotations

from typing import Dict, Tuple

RGB = Tuple[int, int, int]

# Transparency key (optional)
SKY: RGB = (0, 0, 0)

ASSETS: Dict[str, dict] = {}

# Example 2x2 sprite
ASSETS['EXAMPLE'] = {
    'w': 2,
    'h': 2,
    'pix': [
        (255, 0, 0), (0, 255, 0),
        (0, 0, 255), (0, 0, 0),
    ],
}
