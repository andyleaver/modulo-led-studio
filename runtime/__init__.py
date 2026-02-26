from __future__ import annotations

from .particles_v1 import ParticleSystemV1, Particle, Emitter, PointEmitter, LineEmitter, AreaEmitter
from .vector_fields_v1 import (
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
from .noise_v2 import Noise2D, Noise2DConfig, CurlNoise2D, CurlNoiseConfig

from .buffers_v1 import BufferConfig, ScalarBufferV1, VectorBufferV1
from .buffer_advection_v1 import AdvectionConfigV1, advect_scalar_buffer_v1, advect_vector_buffer_v1
from .sampling_v1 import nearest_led_index, splat_scalar_to_leds, normalize_led_buffer

from .shader_math_v1 import clamp01, hash_u32, u01, hsv_to_rgb, add_rgb, gauss

from .force_particles_core_v1 import integrate_point_forces_v1

# Particle rendering primitive
from .particle_render_v1 import (
    ParticleRenderConfigV1,
    render_points_to_leds_v1,
    render_particlesystem_to_leds_v1,
)

# Buffer rendering primitive
from .buffer_render_v1 import (
    BufferRenderConfigV1,
    render_scalar_buffer_to_leds_v1,
    render_vector_buffer_to_leds_v1,
)

from .influence_maps_v1 import DepositConfigV1, SenseConfigV1, deposit_points_scalar_v1, sense_gradient_scalar_v1, steer_follow_gradient_v1

from .integrators_v1 import IntegratorConfigV1, euler_step_entities, apply_drag, clamp_speed

from runtime.system_scheduler_v1 import SystemSchedulerV1

from .particle_pairs_v1 import count_pairs_within_radius_v1

from .constraints_v1 import apply_constraints, BoundsConfigV1, CircleObstacleV1, SegmentObstacleV1, TileMaskObstacleV1

# FSM primitive
from .fsm_v1 import FSMV1, StateV1, TransitionV1, step_fsm_v1, make_phase_fsm_v1


# Long-memory primitives
from .long_memory_v1 import LongMemory2DConfig, LongMemory2D, EventLogV1, EventRecordV1

