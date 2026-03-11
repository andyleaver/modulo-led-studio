"""Compatibility wrapper for the consolidated noise API.

Import from `runtime.noise_fields` in new code. This module re-exports the canonical noise types for older callers.
"""

from __future__ import annotations

# Re-export canonical API
from .noise_fields import (  # noqa: F401
    Noise2D,
    Noise2DConfig,
    CurlNoise2D,
    CurlNoiseConfig,
)
