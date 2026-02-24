from __future__ import annotations

# Phase 3E+ rule:
# - If an effect exists in behaviors/effects and is meant to ship, it MUST be registered here.
# - Selftest will fail if a shipped effect module is present but not registered.
#
# Quarantine policy (temporary):
# - Effects known to render BLANK in the Effect Audit are intentionally *not* registered
#   to keep diagnostics honest and prevent users selecting broken visuals.
# - Quarantined effects remain in the source tree for later repair/rewrite.

from behaviors.effects.solid import register_solid
from behaviors.effects.fade import register_fade
from behaviors.effects.strobe import register_strobe
from behaviors.effects.rainbow import register_rainbow
from behaviors.effects.gradient import register_gradient

from behaviors.effects.chase import register_chase
from behaviors.effects.theater_chase import register_theater_chase
from behaviors.effects.wipe import register_wipe
from behaviors.effects.color_wipe import register_color_wipe
from behaviors.effects.rainbow_wipe import register_rainbow_wipe

from behaviors.effects.scanner import register_scanner, register_sweep
from behaviors.effects.cylon import register_cylon
from behaviors.effects.meteor import register_meteor
from behaviors.effects.juggle import register_juggle
from behaviors.effects.sinelon import register_sinelon

from behaviors.effects.noise import register_noise
from behaviors.effects.wave import register_wave
from behaviors.effects.sparkle import register_sparkle
from behaviors.effects.twinkle import register_twinkle
from behaviors.effects.confetti import register_confetti
from behaviors.effects.pulse import register_pulse
from behaviors.effects.fire import register_fire
from behaviors.effects.bpm import register_bpm
from behaviors.effects.lightning import register_lightning

from behaviors.effects.ripple import register_ripple
from behaviors.effects.aurora import register_aurora
from behaviors.effects.starfield import register_starfield
from behaviors.effects.kaleidoscope import register_kaleidoscope

from behaviors.effects.explosion import register_explosion
from behaviors.effects.comet_storm import register_comet_storm
from behaviors.effects.dna_helix import register_dna_helix
from behaviors.effects.tunnel import register_tunnel

from behaviors.effects.fractal_flame import register_fractal_flame
from behaviors.effects.electric_web import register_electric_web
## QUARANTINED (BLANK in audit)
## from behaviors.effects.liquid_metal import register_liquid_metal
from behaviors.effects.portal import register_portal

from behaviors.effects.shock_chain import register_shock_chain
from behaviors.effects.vortex_particles import register_vortex_particles
from behaviors.effects.impact_ripples import register_impact_ripples
from behaviors.effects.gravity_blobs import register_gravity_blobs

from behaviors.effects.reaction_diffusion import register_reaction_diffusion
from behaviors.effects.volumetric_fog import register_volumetric_fog
from behaviors.effects.plasma_lattice import register_plasma_lattice
from behaviors.effects.glitch_datamosh import register_glitch_datamosh

from behaviors.effects.hyperspace import register_hyperspace
from behaviors.effects.fireworks import register_fireworks
from behaviors.effects.neon_city import register_neon_city
from behaviors.effects.crystal_shards import register_crystal_shards

from behaviors.effects.spectrum_bars_stereo import register_spectrum_bars_stereo
from behaviors.effects.spectral_wave import register_spectral_wave
from behaviors.effects.stereo_energy_field import register_stereo_energy_field

from behaviors.effects.spectral_ripples_14 import register_spectral_ripples_14
## QUARANTINED (BLANK in audit)
## from behaviors.effects.frequency_particles_14 import register_frequency_particles_14
## from behaviors.effects.stereo_call_response import register_stereo_call_response

## QUARANTINED (BLANK in audit)
## from behaviors.effects.spectral_dna_helix_14 import register_spectral_dna_helix_14
from behaviors.effects.stereo_dual_vortex import register_stereo_dual_vortex
from behaviors.effects.spectral_kaleidoscope_audio import register_spectral_kaleidoscope_audio

## QUARANTINED (BLANK in audit)
## from behaviors.effects.beat_strobe import register_beat_strobe
## from behaviors.effects.kick_burst import register_kick_burst
## from behaviors.effects.snare_spark import register_snare_spark

from behaviors.effects.bpm_pulse_train import register_bpm_pulse_train
from behaviors.effects.section_morph_palette import register_section_morph_palette

from behaviors.effects.purpose_meter import register_purpose_meter
from behaviors.effects.audio_meter import register_audio_meter

from behaviors.effects.call_response import register_call_response

from behaviors.effects.audio_zone_eq import register_audio_zone_eq

from behaviors.effects.audio_routed_zones import register_audio_routed_zones
## QUARANTINED (BLANK in audit)
## from behaviors.effects.purpose_bar import register_purpose_bar
## QUARANTINED (BLANK in audit)
## from behaviors.effects.purpose_autoplay import register_purpose_autoplay
from behaviors.effects.demo_asteroids import register_demo_asteroids
from behaviors.effects.demo_breakout import register_demo_breakout

# Full-control primitives
from behaviors.effects.force_particles import register_force_particles
from behaviors.effects.snake_game import register_snake_game
from behaviors.effects.asteroids_game import register_asteroids_game
from behaviors.effects.msgeq7_visualizer_575 import register_msgeq7_visualizer_575
from behaviors.effects.breakout_game import register_breakout_game
from behaviors.effects.snake_game_ino import register_snake_game_ino
from behaviors.effects.blocks_ball_game_ino import register_blocks_ball_game_ino
from behaviors.effects.shooter_game_ino import register_shooter_game_ino
from behaviors.effects.space_invaders_game import register_space_invaders_game
from behaviors.effects.msgeq7_reactive_ino import register_msgeq7_reactive_ino
from behaviors.effects.game_of_life import register_game_of_life
from behaviors.effects.langtons_ant import register_langtons_ant
from behaviors.effects.brians_brain import register_brians_brain
from behaviors.effects.elementary_ca import register_elementary_ca
from behaviors.effects.tilemap_sprite import register_tilemap_sprite
from behaviors.effects.mapping_diagnostics import register_mapping_diagnostics
from behaviors.effects.clock_seconds_dot import register_clock_seconds_dot
from behaviors.effects.clock_hhmm_digits import register_clock_hhmm_digits
from behaviors.effects.mariobros_clockface import register_mariobros_clockface
from behaviors.effects.red_hat_runner import register_red_hat_runner

def register_all():
    # Basics
    register_solid()
    register_fade()
    register_strobe()
    register_rainbow()
    register_gradient()
    # Motion
    register_chase()
    register_theater_chase()
    register_wipe()
    register_color_wipe()
    register_rainbow_wipe()
    register_scanner()
    register_sweep()
    register_cylon()
    register_meteor()
    register_juggle()
    register_sinelon()
    # Texture / Pulse / Energy
    register_noise()
    register_wave()
    register_sparkle()
    register_twinkle()
    register_confetti()
    register_pulse()
    register_fire()
    register_bpm()
    register_lightning()
    # Showcase A
    register_ripple()
    register_aurora()
    register_starfield()
    register_kaleidoscope()
    # Showcase B
    register_explosion()
    register_comet_storm()
    register_dna_helix()
    register_tunnel()

    # Showcase C
    register_fractal_flame()
    register_electric_web()
    # QUARANTINED (BLANK in audit): register_liquid_metal()
    register_portal()
    # Showcase D
    register_shock_chain()
    register_vortex_particles()
    register_impact_ripples()
    register_gravity_blobs()
    # Showcase E
    register_reaction_diffusion()
    register_volumetric_fog()
    register_plasma_lattice()
    register_glitch_datamosh()
    # Showcase F
    register_hyperspace()
    register_fireworks()
    register_neon_city()
    register_crystal_shards()
    # Spectrum Shield Showcase Batch 1
    register_spectrum_bars_stereo()
    register_spectral_wave()
    register_stereo_energy_field()
    # Spectrum Shield Showcase Batch 2
    register_spectral_ripples_14()
    # QUARANTINED (BLANK in audit): register_frequency_particles_14()
    # QUARANTINED (BLANK in audit): register_stereo_call_response()
    # Spectrum Shield Showcase Batch 3 (Hero Demos)
    # QUARANTINED (BLANK in audit): register_spectral_dna_helix_14()
    register_stereo_dual_vortex()
    register_spectral_kaleidoscope_audio()
    # Audio Events Batch 1
    # QUARANTINED (BLANK in audit): register_beat_strobe()
    # QUARANTINED (BLANK in audit): register_kick_burst()
    # QUARANTINED (BLANK in audit): register_snare_spark()
    # Audio Tempo/Sections Batch 2
    register_bpm_pulse_train()
    register_section_morph_palette()
    # Purpose Channels
    register_purpose_meter()
    register_call_response()
    register_audio_zone_eq()
    register_audio_routed_zones()
    register_audio_meter()
    # QUARANTINED (BLANK in audit): register_purpose_bar()
    # QUARANTINED (BLANK in audit): register_purpose_autoplay()
    register_snake_game()
    register_asteroids_game()
    register_msgeq7_visualizer_575()
    register_breakout_game()
    register_demo_asteroids()
    register_demo_breakout()
    # INO Ports (faithful stateful effects)
    register_snake_game_ino()
    register_blocks_ball_game_ino()
    register_shooter_game_ino()
    register_space_invaders_game()
    register_msgeq7_reactive_ino()
    register_game_of_life()
    register_langtons_ant()
    register_brians_brain()
    register_elementary_ca()
    register_tilemap_sprite()
    register_mapping_diagnostics()
    register_clock_seconds_dot()
    register_clock_hhmm_digits()


    register_mariobros_clockface()
    register_red_hat_runner()


# Full-control primitives
    register_force_particles()
