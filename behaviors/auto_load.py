from __future__ import annotations

# Phase 3E+ rule:
# - If an effect exists in behaviors/effects and is meant to ship, it MUST be registered here.
# - Selftest will fail if a shipped effect module is present but not registered.
# Quarantine policy (temporary):
# - Effects known to render BLANK in the Effect Audit are intentionally *not* registered
#   to keep diagnostics honest and prevent users selecting broken visuals.
# - Quarantined effects remain in the source tree for later repair/rewrite.

from behaviors.effects.solid import register_solid
from behaviors.effects.solid_red_1962 import register_solid_red_1962
from behaviors.effects.solid_yellow_1972 import register_solid_yellow_1972
from behaviors.effects.solid_green_era import register_solid_green_era
from behaviors.effects.pulse_red_1980s import register_pulse_red_1980s
from behaviors.effects.pulse_yellow_1980s import register_pulse_yellow_1980s
from behaviors.effects.pulse_green_1980s import register_pulse_green_1980s
from behaviors.effects.fade import register_fade
from behaviors.effects.solid_rgb_mix import register_solid_rgb_mix
from behaviors.effects.solid_white_1996 import register_solid_white_1996
from behaviors.effects.matrix_dot import register_matrix_dot
from behaviors.effects.matrix_scroll_bar import register_matrix_scroll_bar
from behaviors.effects.clock_seconds_dot import register_clock_seconds_dot
from behaviors.effects.memory_heatmap import register_memory_heatmap
from behaviors.effects.boids_swarm import register_boids_swarm
from behaviors.effects.fsm_phases import register_fsm_phases
from behaviors.effects.strobe import register_strobe
from behaviors.effects.rainbow import register_rainbow
from behaviors.effects.gradient import register_gradient
from behaviors.effects.kernel import register_kernel
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

def register_all():
    # Basics
    register_solid()
    register_solid_red_1962()
    register_solid_yellow_1972()
    register_solid_green_era()
    register_pulse_red_1980s()
    register_pulse_yellow_1980s()
    register_pulse_green_1980s()
    register_fade()
    register_solid_rgb_mix()
    register_solid_white_1996()
    register_matrix_dot()
    register_matrix_scroll_bar()
    register_clock_seconds_dot()
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
    # Modulo showcase / full-power layer primitives
    register_memory_heatmap()
    register_boids_swarm()
    register_fsm_phases()
    # Escape hatch (advanced)
    register_kernel()
