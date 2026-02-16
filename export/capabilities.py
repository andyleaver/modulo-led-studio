"""Export Target Capability Profiles (Phase C scaffold)

This module defines explicit capabilities for export targets.
It is intentionally conservative and may not be wired everywhere yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetCapabilities:
    name: str

    # Audio
    supports_audio_msgeq7: bool = False
    supports_stereo: bool = False
    supports_bands: bool = False

    # Modulotion
    supports_modulotion: bool = False  # keep false for beta

    # General limits
    max_layers_exportable: int = 1


# Conservative defaults
ARDUINO_FASTLED_BASIC = TargetCapabilities(
    name="arduino_fastled_basic",
    supports_audio_msgeq7=False,
    supports_stereo=False,
    supports_bands=False,
    supports_modulotion=False,
    max_layers_exportable=1,
)

ARDUINO_FASTLED_MSGEQ7_STEREO = TargetCapabilities(
    name="arduino_fastled_msgeq7_stereo",
    supports_audio_msgeq7=True,
    supports_stereo=True,
    supports_bands=True,
    supports_modulotion=False,
    max_layers_exportable=1,
)
