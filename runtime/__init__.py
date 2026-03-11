from __future__ import annotations

from .particles import ParticleSystem, Particle, Emitter, PointEmitter, LineEmitter, AreaEmitter, surface_bounds_from_snapshot, layout_bounds_from_snapshot
from .vector_fields import (
    VectorField,
    ConstantField,
    ConstantFieldConfig,
    RadialField,
    RadialFieldConfig,
    VortexField,
    VortexFieldConfig,
    CurlNoiseField,
    CurlNoiseFieldConfig,
)
from .noise_fields import Noise2D, Noise2DConfig, CurlNoise2D, CurlNoiseConfig
from .buffers import BufferConfig, ScalarBuffer, VectorBuffer
from .buffer_advection import AdvectionConfig, advect_scalar_buffer, advect_vector_buffer
from .sampling import (
    nearest_surface_led_index,
    splat_scalar_to_surface_leds,
    nearest_led_index,
    splat_scalar_to_leds,
    normalize_led_buffer,
)
from .shader_math import clamp01, hash_u32, u01, hsv_to_rgb, add_rgb, gauss
from .force_particles_core import integrate_point_forces
from .particle_render import (
    ParticleRenderConfig,
    render_points_to_surface_leds,
    render_particle_system_to_surface_leds,
    render_points_to_leds,
    render_particle_system_to_leds,
)
from .buffer_render import (
    BufferRenderConfig,
    render_scalar_buffer_to_surface_leds,
    render_vector_buffer_to_surface_leds,
    render_scalar_buffer_to_leds,
    render_vector_buffer_to_leds,
)
from .influence_maps import DepositConfig, SenseConfig, deposit_points_scalar, sense_gradient_scalar, steer_follow_gradient
from .integrators import IntegratorConfig, euler_step_entities, apply_drag, clamp_speed
from .system_scheduler import SystemScheduler
from .particle_pairs import count_pairs_within_radius
from .constraints import apply_constraints, BoundsConfig, CircleObstacle, SegmentObstacle, TileMaskObstacle
from .fsm import FSM, State, Transition, step_fsm, make_phase_fsm
from .long_memory import LongMemory2DConfig, LongMemory2D, EventLog, EventRecord

from .spatial_transform import (
    led_to_surface_xy,
    surface_to_world,
    world_to_surface,
    world_to_surface_led_index,
    led_to_layout_xy,
    layout_to_world,
    world_to_layout,
    world_to_led_index,
)
