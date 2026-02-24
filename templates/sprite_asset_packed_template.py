"""Sprite asset *packed* template.

This is a suggested shape for packed assets that are friendly to AVR-class RAM.
Design goals:
- Palette <= 256 colors.
- Per-sprite pixel stream is indexed bytes (0..len(PALETTE)-1).
- Optional RLE encoding for further compression.

The engine/exporter may choose to use raw ASSETS for preview and PACKED_* for firmware.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]

PALETTE: List[RGB] = [
    (0, 0, 0),
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
]

# RLE format: list of (count, palette_index)
# count is 1..255
PACKED_ASSETS: Dict[str, dict] = {
    'EXAMPLE': {
        'w': 2,
        'h': 2,
        'rle': [(1, 1), (1, 2), (1, 3), (1, 0)],
    }
}
