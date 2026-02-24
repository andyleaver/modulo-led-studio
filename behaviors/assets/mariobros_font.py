from __future__ import annotations

from pathlib import Path

from .adafruit_gfx_font import load_gfx_font_from_header


def load_super_mario_font():
    root = Path(__file__).resolve().parents[2]
    header = root / 'third_party' / 'mariobros_clock' / 'Super_Mario_Bros__24pt7b.h'
    # In header, the font struct is named 'Super_Mario_Bros__24pt7b'
    return load_gfx_font_from_header(header, 'Super_Mario_Bros__24pt7b')


# Lazy singleton
_FONT = None


def get_font():
    global _FONT
    if _FONT is None:
        _FONT = load_super_mario_font()
    return _FONT
