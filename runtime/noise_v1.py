"""DEPRECATED: noise_v1

This module is kept for backward compatibility.
New code should import from `runtime.noise_v2`.

v1 originally provided CurlNoise2D/CurlNoiseConfig; v2 consolidates and extends noise support.
"""

from __future__ import annotations

# Re-export v2 API
from .noise_v2 import (  # noqa: F401
    Noise2D,
    Noise2DConfig,
    CurlNoise2D,
    CurlNoiseConfig,
)
