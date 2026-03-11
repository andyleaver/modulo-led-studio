"""
Export Eligibility Matrix

Single source of truth for whether a behavior is:
- exportable
- preview-only
- blocked (with reason)

Policy (engine-grade):
- This table reflects ONLY the effects we actually ship/register for the standard LED-app path.
- Non-standard experiments / showcases are intentionally removed from the shipped registry.
- Legacy keys may be imported via project normalization, but runtime/export truth is canonical.
"""

from dataclasses import dataclass
from typing import Dict

class ExportStatus:
    EXPORTABLE = "exportable"
    PREVIEW_ONLY = "preview-only"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class Eligibility:
    status: str
    reason: str = ""

# Key must match behavior registry keys exactly
# Standard LED-app effects + Era tutorial basics + Escape hatch.
EXPORT_ELIGIBILITY: Dict[str, Eligibility] = {
    # Era tutorial basics
    "solid_red_1962": Eligibility(ExportStatus.EXPORTABLE),
    "solid_yellow_1972": Eligibility(ExportStatus.EXPORTABLE),
    "solid_green_era": Eligibility(ExportStatus.EXPORTABLE),
    "pulse_red_1980s": Eligibility(ExportStatus.EXPORTABLE),
    "pulse_yellow_1980s": Eligibility(ExportStatus.EXPORTABLE),
    "pulse_green_1980s": Eligibility(ExportStatus.EXPORTABLE),
    "solid_rgb_mix": Eligibility(ExportStatus.EXPORTABLE),
    "solid_white_1996": Eligibility(ExportStatus.EXPORTABLE),
    "matrix_dot": Eligibility(ExportStatus.PREVIEW_ONLY, "Historical matrix tutorial effect is preview-only"),
    "matrix_scroll_bar": Eligibility(ExportStatus.PREVIEW_ONLY, "Historical matrix tutorial effect is preview-only"),
    "clock_seconds_dot": Eligibility(ExportStatus.PREVIEW_ONLY, "Historical matrix tutorial effect is preview-only"),

    # Core standard effects
    "solid": Eligibility(ExportStatus.EXPORTABLE),
    "fade": Eligibility(ExportStatus.EXPORTABLE),
    "strobe": Eligibility(ExportStatus.EXPORTABLE),
    "pulse": Eligibility(ExportStatus.EXPORTABLE),
    "bpm": Eligibility(ExportStatus.EXPORTABLE),

    "rainbow": Eligibility(ExportStatus.EXPORTABLE),
    "gradient": Eligibility(ExportStatus.EXPORTABLE),

    "chase": Eligibility(ExportStatus.EXPORTABLE),
    "theater_chase": Eligibility(ExportStatus.EXPORTABLE),
    "wipe": Eligibility(ExportStatus.EXPORTABLE),
    "color_wipe": Eligibility(ExportStatus.EXPORTABLE),
    "rainbow_wipe": Eligibility(ExportStatus.EXPORTABLE),

    "scanner": Eligibility(ExportStatus.EXPORTABLE),
    "sweep": Eligibility(ExportStatus.EXPORTABLE),
    "cylon": Eligibility(ExportStatus.EXPORTABLE),
    "meteor": Eligibility(ExportStatus.EXPORTABLE),
    "juggle": Eligibility(ExportStatus.EXPORTABLE),
    "sinelon": Eligibility(ExportStatus.EXPORTABLE),

    "noise": Eligibility(ExportStatus.EXPORTABLE),
    "wave": Eligibility(ExportStatus.EXPORTABLE),

    "sparkle": Eligibility(ExportStatus.EXPORTABLE),
    "twinkle": Eligibility(ExportStatus.EXPORTABLE),
    "confetti": Eligibility(ExportStatus.EXPORTABLE),

    "fire": Eligibility(ExportStatus.EXPORTABLE),
    "lightning": Eligibility(ExportStatus.EXPORTABLE),

    # Escape hatch (advanced)
    "kernel": Eligibility(ExportStatus.EXPORTABLE),  # Requires params.cpp body; exporter validates.
    # Shipped advanced/preview behaviors
    "boids_swarm": Eligibility(ExportStatus.PREVIEW_ONLY, "Advanced agent behavior is preview-only"),
    "fsm_phases": Eligibility(ExportStatus.PREVIEW_ONLY, "Advanced phase/state behavior is preview-only"),
    "memory_heatmap": Eligibility(ExportStatus.PREVIEW_ONLY, "Long-memory behavior is preview-only"),
}

# Back-compat alias (tools expect ELIGIBILITY)
ELIGIBILITY = EXPORT_ELIGIBILITY

def get_eligibility(behavior_key: str) -> Eligibility:
    return EXPORT_ELIGIBILITY.get(
        behavior_key,
        Eligibility(ExportStatus.PREVIEW_ONLY, "Not yet classified for export")
    )
