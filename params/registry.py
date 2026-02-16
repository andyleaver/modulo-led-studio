# Parameter registry (single source of truth)
# - All tweakable knobs live here (even if not yet used by an effect).
# - Effects declare which knobs they use via their `USES` list in behaviors/effects/*.py
#
# Types supported by AutoParamPanel + resolve():
#   float, int, bool, enum, rgb

from __future__ import annotations

PARAMS: dict[str, dict] = {
    # Core toggles / meta
    "enabled":      {"type": "bool",  "default": True},
    "opacity":      {"type": "float", "default": 1.0, "min": 0.0, "max": 1.0},

    # Colors
    "color":        {"type": "rgb",   "default": (255, 0, 0)},
    "color2":       {"type": "rgb",   "default": (0, 0, 255)},
    "bg":           {"type": "rgb",   "default": (0, 0, 0)},  # friendly alias for background

    # Enums
    "direction":    {"type": "enum",  "default": "forward", "choices": ["forward", "reverse"]},
    "palette":      {"type": "enum",  "default": "rainbow", "choices": ["rainbow", "heat", "ocean", "forest", "mono"]},
    "blend_mode":   {"type": "enum",  "default": "over", "choices": ["over", "add", "mul", "max"]},

    # Common effect controls
    "brightness":   {"type": "float", "default": 1.0, "min": 0.0, "max": 1.0},
    # PostFX / Operators
    # A simple multiplier applied after the base operator.
    "gain":         {"type": "float", "label": "Gain", "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.01, "decimals": 2},
    # Gamma curve applied per-channel: out = 255 * (in/255) ** gamma
    # gamma < 1 brightens mid-tones; gamma > 1 darkens.
    "gamma":        {"type": "float", "label": "Gamma", "default": 1.0, "min": 0.2, "max": 3.0, "step": 0.01, "decimals": 2},
    "clamp_min":    {"type": "float", "label": "Clamp Min", "default": 0.0, "min": 0.0, "max": 255.0, "step": 1.0, "decimals": 0},
    "clamp_max":    {"type": "float", "label": "Clamp Max", "default": 255.0, "min": 0.0, "max": 255.0, "step": 1.0, "decimals": 0},
    "posterize_levels": {"type": "float", "label": "Posterize Levels", "default": 6.0, "min": 2.0, "max": 32.0, "step": 1.0, "decimals": 0},
    "threshold":    {"type": "float", "label": "Threshold", "default": 128.0, "min": 0.0, "max": 255.0, "step": 1.0, "decimals": 0},
    "speed":        {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0},
    "snake_speed":  {"type": "float", "default": 8.0, "min": 0.5, "max": 25.0},  # moves/sec for Snake
    "width":        {"type": "float", "default": 4.0, "min": 1.0, "max": 200.0},   # effect-specific meaning
    "softness":     {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0},
    "density":      {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0},
    "duty":         {"type": "float", "default": 0.25, "min": 0.0, "max": 1.0},
    "strobe_hz":    {"type": "float", "default": 8.0, "min": 0.1, "max": 40.0},
    "fade":         {"type": "float", "default": 0.15, "min": 0.0, "max": 1.0},
    "bleed_amount": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0},
    "bleed_radius": {"type": "int",   "default": 1,   "min": 1,   "max": 12},
    "trail_amount": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0},

    # Palette / hue controls
    "hue_offset":   {"type": "int",   "default": 0, "min": 0, "max": 255},
    "hue_span":     {"type": "float", "default": 1.0, "min": 0.0, "max": 8.0},

    # Game / simulation knobs (foundation; used later)
    "block_health": {"type": "int",   "default": 3, "min": 1, "max": 20},
    "lives":        {"type": "int",   "default": 3, "min": 1, "max": 9},
    "score_target": {"type": "int",   "default": 50, "min": 1, "max": 9999},

    "enemy_count":  {"type": "int",   "default": 8, "min": 0, "max": 200},
    "spawn_rate":   {"type": "float", "default": 1.0, "min": 0.0, "max": 40.0},   # per second
    "fire_rate":    {"type": "float", "default": 4.0, "min": 0.2, "max": 40.0},   # shots per second
    "shot_speed":   {"type": "float", "default": 10.0, "min": 0.1, "max": 80.0},
    "ball_speed":   {"type": "float", "default": 8.0, "min": 0.1, "max": 80.0},
    "paddle_width": {"type": "int",   "default": 8, "min": 1, "max": 300},

    "snake_length": {"type": "int",   "default": 6, "min": 1, "max": 999},
    "food_rate":    {"type": "float", "default": 0.7, "min": 0.0, "max": 10.0},   # per second
    "wrap_edges":   {"type": "bool",  "default": True},
    "edge_mode":   {"type": "enum",  "default": "wrap", "choices": ["wrap", "bounce", "destroy"]},
    "rng_seed":   {"type": "int",   "default": 1337, "min": 0, "max": 2147483647, "widget": "spin"},
    "fixed_step_hz": {"type": "int", "default": 60, "min": 10, "max": 240, "widget": "spin"},
    "max_substeps": {"type": "int", "default": 5, "min": 1, "max": 50, "widget": "spin"},
    "pp_mode":     {"type": "enum",  "default": "off", "choices": ["off", "collision", "near", "both"]},
    "pp_radius":   {"type": "float", "default": 1.25, "min": 0.25, "max": 20.0, "step": 0.05},
    "pp_max_pairs":{"type": "int",   "default": 2000, "min": 0, "max": 200000, "widget": "spin"},

    "purpose_f0":  {"type":"float","default":0.0,"min":0.0,"max":1.0},  # purpose float channel 0
    "purpose_f1":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_f2":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_f3":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_f4":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_f5":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_f6":  {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "purpose_speed": {"type":"float","default":0.35,"min":0.0,"max":5.0},
    "purpose_decay": {"type":"float","default":0.92,"min":0.0,"max":1.0},
    "purpose_i0":  {"type":"int","default":0,"min":-32768,"max":32767},
    "purpose_i1":  {"type":"int","default":0,"min":-32768,"max":32767},
    "purpose_i2":  {"type":"int","default":0,"min":-32768,"max":32767},
    "purpose_i3":  {"type":"int","default":0,"min":-32768,"max":32767},

    # liquid_metal
    "lm_speed": {"type":"float","default":0.22,"min":0.0,"max":5.0},
    "lm_brightness": {"type":"float","default":1.0,"min":0.0,"max":1.0},
    "lm_palette_mode": {"type":"float","default":0.0,"min":0.0,"max":3.0},
    "lm_tint": {"type":"float","default":0.0,"min":0.0,"max":1.0},
    "lm_contrast": {"type":"float","default":0.65,"min":0.0,"max":2.0},
    "lm_density": {"type":"float","default":0.35,"min":0.0,"max":1.0},
    "lm_glow": {"type":"float","default":0.55,"min":0.0,"max":1.0},

    "gravity":      {"type": "float", "default": 0.0, "min": -50.0, "max": 50.0},
    "friction":     {"type": "float", "default": 0.0, "min": 0.0, "max": 10.0},

    # Forces (Simulation building blocks)
    # Used by Force Particles and future object-based simulations.
    "force_mode":   {"type": "enum",  "default": "attract", "choices": ["attract", "repel"]},
    "force_source": {"type": "enum", "default": "center", "choices": ["center", "fixed"]},
    "source_x":     {"type": "float","default": 0.0, "min": -9999.0, "max": 9999.0},
    "source_y":     {"type": "float","default": 0.0, "min": -9999.0, "max": 9999.0},
    "pairwise_repel": {"type": "bool", "default": False},
    "repel_strength": {"type": "float", "default": 4.0, "min": 0.0, "max": 50.0},
    "repel_range":    {"type": "float", "default": 6.0, "min": 0.0, "max": 200.0},

    # Variable bindings (): optional variable name to drive this force.
    # If set, the force value is multiplied by the variable's current number value.
    "gravity_bind_var": {"type": "string", "default": ""},
    "gravity_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},
    "repel_strength_bind_var": {"type": "string", "default": ""},
    "repel_strength_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},

    # : System/particle variable bindings (per-effect variables).
    # If set, the corresponding sim knob is multiplied by the variable's current number value.
    "enemy_count_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "enemy_count_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},
    "speed_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "speed_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},
    "friction_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "friction_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},

    # : Continuous spawning controls (Force Particles)
    "max_entities": {"type": "int", "default": 80, "min": 0, "max": 500, "widget": "spin"},
    "max_entities_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "max_entities_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},
    "spawn_rate_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "spawn_rate_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},

    # : Lifetime controls (Force Particles)
    "lifetime": {"type": "float", "default": 0.0, "min": 0.0, "max": 20.0},
    "lifetime_bind_var": {"type": "enum", "default": "", "choices_fn": "number_vars"},
    "lifetime_bind_layer": {"type": "int", "default": -1, "min": -1, "max": 32, "widget": "spin"},

    # Rules MVP (Simulation building blocks)
    # A simple "dot" target that can spawn and be collected by moving objects.
    "dot_enabled":        {"type": "bool",  "default": False},
    "dot_color":          {"type": "rgb",   "default": (0, 255, 0)},
    "dot_spawn_mode":     {"type": "enum",  "default": "on_hit", "choices": ["on_hit", "timer"]},
    "dot_spawn_interval": {"type": "float", "default": 1.0, "min": 0.1, "max": 30.0},

    # Conway's Game of Life
    "life_step_hz":    {"type": "int",   "label": "Life Step Hz", "default": 8, "min": 1, "max": 60, "widget": "spin"},
    "life_wrap":       {"type": "bool",  "label": "Life Wrap", "default": True},
    "life_seed":       {"type": "int",   "label": "Life Seed", "default": 1337, "min": 0, "max": 2147483647, "widget": "spin"},
    "life_strip_width":{"type": "int",   "label": "Strip Width", "default": 32, "min": 1, "max": 512, "widget": "spin"},
    "life_variant":    {"type": "enum",  "label": "Life Variant", "default": "Conway", "choices": ["Conway", "HighLife", "Seeds", "DayNight"]},

    # Langton's Ant
    "ant_step_hz":     {"type": "int",  "label": "Ant Step Hz", "default": 30, "min": 1, "max": 240, "widget": "spin"},
    "ant_wrap":        {"type": "bool", "label": "Ant Wrap", "default": True},
    "ant_seed":        {"type": "int",  "label": "Ant Seed", "default": 1, "min": 0, "max": 2147483647, "widget": "spin"},
    "ant_strip_width": {"type": "int",  "label": "Strip Width", "default": 32, "min": 1, "max": 512, "widget": "spin"},
    "ant_color":       {"type": "rgb",  "label": "Ant Color", "default": (255, 0, 0)},

    # Elementary Cellular Automaton (Rule 0..255)
    "ca_rule":         {"type": "int",  "label": "CA Rule", "default": 30, "min": 0, "max": 255, "widget": "spin"},
    "ca_step_hz":      {"type": "int",  "label": "CA Step Hz", "default": 20, "min": 1, "max": 240, "widget": "spin"},
    "ca_wrap":         {"type": "bool", "label": "CA Wrap", "default": True},
    "ca_seed":         {"type": "int",  "label": "CA Seed", "default": 1, "min": 0, "max": 2147483647, "widget": "spin"},
    "ca_strip_width":  {"type": "int",  "label": "Strip Width", "default": 0, "min": 0, "max": 512, "widget": "spin"},

    # Brian's Brain
    "brain_step_hz":    {"type": "int",  "label": "Brain Step Hz", "default": 12, "min": 1, "max": 240, "widget": "spin"},
    "brain_wrap":       {"type": "bool", "label": "Brain Wrap", "default": True},
    "brain_seed":       {"type": "int",  "label": "Brain Seed", "default": 42, "min": 0, "max": 2147483647, "widget": "spin"},
    "brain_strip_width":{"type": "int",  "label": "Strip Width", "default": 32, "min": 1, "max": 512, "widget": "spin"},
    "brain_dying_color":{"type": "rgb",  "label": "Dying Color", "default": (0, 0, 255)},
}

def numeric_param_keys():
    return [k for k, spec in PARAMS.items() if spec.get("type") in ("float","int")]

# Sources for modulotors. Audio sources are normalized 0..1 and converted to bipolar in Modulotor.sample.
SOURCES = [
    "none",
    "lfo_sine",
    "audio_energy",
    "audio_mono0",
    "audio_mono1",
    "audio_mono2",
    "audio_mono3",
    "audio_mono4",
    "audio_mono5",
    "audio_mono6",
    "audio_L0",
    "audio_L1",
    "audio_L2",
    "audio_L3",
    "audio_L4",
    "audio_L5",
    "audio_L6",
    "audio_R0",
    "audio_R1",
    "audio_R2",
    "audio_R3",
    "audio_R4",
    "audio_R5",
    "audio_R6",
    "audio_beat",
    "audio_kick",
    "audio_snare",
    "audio_onset",
    "audio_bpm",
    "audio_bpm_conf",
    "audio_sec_change",
    "audio_sec_id",
    "audio_tr_L0",
    "audio_tr_L1",
    "audio_tr_L2",
    "audio_tr_L3",
    "audio_tr_L4",
    "audio_tr_L5",
    "audio_tr_L6",
    "audio_tr_R0",
    "audio_tr_R1",
    "audio_tr_R2",
    "audio_tr_R3",
    "audio_tr_R4",
    "audio_tr_R5",
    "audio_tr_R6",
    "audio_pk_L0",
    "audio_pk_L1",
    "audio_pk_L2",
    "audio_pk_L3",
    "audio_pk_L4",
    "audio_pk_L5",
    "audio_pk_L6",
    "audio_pk_R0",
    "audio_pk_R1",
    "audio_pk_R2",
    "audio_pk_R3",
    "audio_pk_R4",
    "audio_pk_R5",
    "audio_pk_R6",
    "purpose_f0",
    "purpose_f1",
    "purpose_f2",
    "purpose_f3",
    "purpose_i0",
    "purpose_i1",
    "purpose_i2",
    "purpose_i3",
    "purpose_score",
    "purpose_blocks_left",
]


MODES = ["add","mul","set"]

def default_params_for_behavior(behavior_key: str) -> dict:
    """Return a fresh params dict containing defaults for a behavior's declared uses."""
    from behaviors.registry import REGISTRY
    b = REGISTRY.get(str(behavior_key).lower().strip())
    if not b:
        return {}
    out = {}
    for k in (b.uses or []):
        meta = PARAMS.get(k, {})
        if "default" in meta:
            v = meta["default"]
            out[k] = list(v) if isinstance(v, (list, tuple)) else v
    return out