"""
Export Eligibility Matrix (Step 1)

Single source of truth for whether a behavior is:
- exportable
- preview-only
- blocked (with reason)

In this build, the table is fully populated from shipped behavior keys.
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
EXPORT_ELIGIBILITY: Dict[str, Eligibility] = {
    "asteroids_game": Eligibility(ExportStatus.BLOCKED, "Asteroids (Game) is preview-ready but Arduino export is not wired yet."),
    "audio_routed_zones": Eligibility(ExportStatus.EXPORTABLE),
    "audio_zone_eq": Eligibility(ExportStatus.EXPORTABLE),
    "audio_meter": Eligibility(ExportStatus.PREVIEW_ONLY, "Audio Meter is a rules-driven preview utility; Arduino export is not implemented yet."),
    "aurora": Eligibility(ExportStatus.EXPORTABLE),
    "beat_strobe": Eligibility(ExportStatus.EXPORTABLE),
    "blocks_ball_game_ino": Eligibility(ExportStatus.BLOCKED, "Blocks+Ball (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter."),
    "bpm": Eligibility(ExportStatus.EXPORTABLE),
    "bpm_pulse_train": Eligibility(ExportStatus.EXPORTABLE),
    "breakout_game": Eligibility(ExportStatus.BLOCKED, "Breakout (Game) is preview-ready but Arduino export is not wired yet."),
    "brians_brain": Eligibility(ExportStatus.BLOCKED, "Export not yet supported for Brian's Brain (preview only for now)."),
    "call_response": Eligibility(ExportStatus.EXPORTABLE),
    "chase": Eligibility(ExportStatus.EXPORTABLE),
    "color_wipe": Eligibility(ExportStatus.EXPORTABLE),
    "comet_storm": Eligibility(ExportStatus.EXPORTABLE),
    "confetti": Eligibility(ExportStatus.EXPORTABLE),
    "crystal_shards": Eligibility(ExportStatus.EXPORTABLE),
    "cylon": Eligibility(ExportStatus.EXPORTABLE),
    "demo_asteroids": Eligibility(ExportStatus.EXPORTABLE),
    "demo_breakout": Eligibility(ExportStatus.EXPORTABLE),
    "dna_helix": Eligibility(ExportStatus.EXPORTABLE),
    "electric_web": Eligibility(ExportStatus.EXPORTABLE),
    "elementary_ca": Eligibility(ExportStatus.BLOCKED, "Export not yet supported for Elementary CA (preview only for now)."),
    "explosion": Eligibility(ExportStatus.EXPORTABLE),
    "fade": Eligibility(ExportStatus.EXPORTABLE),
    "fire": Eligibility(ExportStatus.EXPORTABLE),
    "fireworks": Eligibility(ExportStatus.EXPORTABLE),
    "force_particles": Eligibility(ExportStatus.EXPORTABLE),
    "fractal_flame": Eligibility(ExportStatus.EXPORTABLE),
    "frequency_particles_14": Eligibility(ExportStatus.EXPORTABLE),
    "game_of_life": Eligibility(ExportStatus.BLOCKED, "Export not yet supported for Game of Life (preview only for now)."),
    "glitch_datamosh": Eligibility(ExportStatus.EXPORTABLE),
    "gradient": Eligibility(ExportStatus.EXPORTABLE),
    "gravity_blobs": Eligibility(ExportStatus.EXPORTABLE),
    "hyperspace": Eligibility(ExportStatus.EXPORTABLE),
    "impact_ripples": Eligibility(ExportStatus.EXPORTABLE),
    "juggle": Eligibility(ExportStatus.EXPORTABLE),
    "kaleidoscope": Eligibility(ExportStatus.EXPORTABLE),
    "kick_burst": Eligibility(ExportStatus.EXPORTABLE),
    "langtons_ant": Eligibility(ExportStatus.BLOCKED, "Export not yet supported for Langton's Ant (preview only for now)."),
    "lightning": Eligibility(ExportStatus.EXPORTABLE),
    "liquid_metal": Eligibility(ExportStatus.EXPORTABLE),
    "meteor": Eligibility(ExportStatus.EXPORTABLE),
    "msgeq7_reactive_ino": Eligibility(ExportStatus.BLOCKED, "MSGEQ7 Reactive (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter."),
    "msgeq7_visualizer_575": Eligibility(ExportStatus.BLOCKED, "MSGEQ7 Visualizer (575) is preview-ready but Arduino export is not wired yet."),
    "neon_city": Eligibility(ExportStatus.EXPORTABLE),
    "noise": Eligibility(ExportStatus.EXPORTABLE),
    "plasma_lattice": Eligibility(ExportStatus.EXPORTABLE),
    "portal": Eligibility(ExportStatus.EXPORTABLE),
    "pulse": Eligibility(ExportStatus.EXPORTABLE),
    "purpose_autoplay": Eligibility(ExportStatus.EXPORTABLE),
    "purpose_bar": Eligibility(ExportStatus.EXPORTABLE),
    "purpose_meter": Eligibility(ExportStatus.EXPORTABLE),
    "rainbow": Eligibility(ExportStatus.EXPORTABLE),
    "rainbow_wipe": Eligibility(ExportStatus.EXPORTABLE),
    "reaction_diffusion": Eligibility(ExportStatus.EXPORTABLE),
    "ripple": Eligibility(ExportStatus.EXPORTABLE),
    "scanner": Eligibility(ExportStatus.EXPORTABLE),
    "section_morph_palette": Eligibility(ExportStatus.EXPORTABLE),
    "shock_chain": Eligibility(ExportStatus.EXPORTABLE),
    "shooter_game_ino": Eligibility(ExportStatus.BLOCKED, "Shooter (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter."),
    "sinelon": Eligibility(ExportStatus.EXPORTABLE),
    "snake_game": Eligibility(ExportStatus.BLOCKED, "Snake (Game) is preview-ready but Arduino export is not wired yet."),
    "snake_game_ino": Eligibility(ExportStatus.BLOCKED, "Snake (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter."),
    "snare_spark": Eligibility(ExportStatus.EXPORTABLE),
    "solid": Eligibility(ExportStatus.EXPORTABLE),
    "space_invaders_game": Eligibility(ExportStatus.BLOCKED, "Space Invaders (Game) is preview-ready but Arduino export is not wired yet."),
    "sparkle": Eligibility(ExportStatus.EXPORTABLE),
    "spectral_dna_helix_14": Eligibility(ExportStatus.EXPORTABLE),
    "spectral_kaleidoscope_audio": Eligibility(ExportStatus.EXPORTABLE),
    "spectral_ripples_14": Eligibility(ExportStatus.EXPORTABLE),
    "spectral_wave": Eligibility(ExportStatus.EXPORTABLE),
    "spectrum_bars_stereo": Eligibility(ExportStatus.EXPORTABLE),
    "starfield": Eligibility(ExportStatus.EXPORTABLE),
    "stereo_call_response": Eligibility(ExportStatus.EXPORTABLE),
    "stereo_dual_vortex": Eligibility(ExportStatus.EXPORTABLE),
    "stereo_energy_field": Eligibility(ExportStatus.EXPORTABLE),
    "strobe": Eligibility(ExportStatus.EXPORTABLE),
    "theater_chase": Eligibility(ExportStatus.EXPORTABLE),
    "tunnel": Eligibility(ExportStatus.EXPORTABLE),
    "twinkle": Eligibility(ExportStatus.EXPORTABLE),
    "volumetric_fog": Eligibility(ExportStatus.EXPORTABLE),
    "vortex_particles": Eligibility(ExportStatus.EXPORTABLE),
    "wave": Eligibility(ExportStatus.EXPORTABLE),
    "wipe": Eligibility(ExportStatus.EXPORTABLE),
}

def get_eligibility(behavior_key: str) -> Eligibility:
    return EXPORT_ELIGIBILITY.get(
        behavior_key,
        Eligibility(ExportStatus.PREVIEW_ONLY, "Not yet classified for export")
    )
