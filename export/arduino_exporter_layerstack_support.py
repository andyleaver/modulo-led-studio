from __future__ import annotations

BEHAVIOR_IDS = {
    "solid":0, "chase":1, "wipe":2, "sparkle":3, "scanner":4, "fade":5, "strobe":6,
    "rainbow":7, "bouncer":8, "breakout_lite":9, "breakout_game":9, "demo_breakout":9,
    "asteroids_lite":10, "asteroids_game":10, "demo_asteroids":10, "tilemap_sprite":11,
    "red_hat_runner":11, "mariobros_clockface":11, "brians_brain":12, "game_of_life":12,
    "elementary_ca":12, "langtons_ant":12, "msgeq7_visualizer_575":13,
    "msgeq7_reactive_ino":13, "snake_game":14, "snake_game_ino":14, "space_invaders_game":15,
    "shooter_game_ino":16, "blocks_ball_game_ino":17, "kernel_dsl":22, "kernel":23,
    "fsm_phases":23, "ca_module":12, "boids_swarm":18, "predator_prey":19,
    "memory_heatmap":20, "ambient_dashboard":21,
}

OPS_PER_LAYER = 2
MODS_PER_LAYER = 2

OPERATOR_KIND_IDS = {
    "none": 0,
    "gain": 1,
    "gamma": 2,
    "posterize": 3,
}

SOURCE_IDS = {"none":0, "lfo_sine":1, "energy":10, "audio_energy":10}
for _i in range(7):
    SOURCE_IDS[f"mono{_i}"] = 11 + _i
    SOURCE_IDS[f"l{_i}"] = 21 + _i
    SOURCE_IDS[f"r{_i}"] = 31 + _i
    SOURCE_IDS[f"audio_mono{_i}"] = 11 + _i
    SOURCE_IDS[f"audio_L{_i}"] = 21 + _i
    SOURCE_IDS[f"audio_R{_i}"] = 31 + _i
SOURCE_IDS.update({
    "purpose_f0":50, "purpose_f1":51, "purpose_f2":52, "purpose_f3":53,
    "purpose_i0":54, "purpose_i1":55, "purpose_i2":56, "purpose_i3":57,
})

CURVE_IDS = {"linear":0, "invert":1, "abs":2, "pow2":3, "pow3":4}
MODE_IDS = {"mul":0, "add":1, "set":2}
TARGET_PARAM_IDS = {
    "brightness":0, "speed":1, "width":2, "softness":3, "density":4, "direction":5,
    "purpose_f0":6, "purpose_f1":7, "purpose_f2":8, "purpose_f3":9,
    "purpose_i0":10, "purpose_i1":11, "purpose_i2":12, "purpose_i3":13,
}


def clamp01(value):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def csv_values(values):
    return ",".join(str(v) for v in values)


def resolve_ui_target_mask_set(project, num_leds, *, resolve_address, resolve_mask_to_indices):
    try:
        ui_target_mask_key = resolve_address(project=project, address="project.ui.target_mask", default=None).value
    except Exception:
        ui_target_mask_key = None
    try:
        if isinstance(ui_target_mask_key, str) and ui_target_mask_key.strip():
            return set(resolve_mask_to_indices(project, ui_target_mask_key, n=num_leds))
    except Exception:
        return set()
    return set()


def build_group_index_maps(groups, num_leds):
    group_sets = []
    group_set_to_id = {}
    for gi, group in enumerate(list(groups)):
        indices = group.get("indices", []) if isinstance(group, dict) else []
        try:
            as_set = frozenset(int(v) for v in (indices or []) if 0 <= int(v) < num_leds)
        except Exception:
            as_set = frozenset()
        group_sets.append(as_set)
        if as_set and as_set not in group_set_to_id:
            group_set_to_id[as_set] = gi
    return group_sets, group_set_to_id


def ensure_group_for_indices(*, groups, group_sets, group_set_to_id, num_leds, indices):
    frozen = frozenset(sorted(int(v) for v in indices if 0 <= int(v) < num_leds))
    if not frozen:
        return -1
    if frozen in group_set_to_id:
        return int(group_set_to_id[frozen])
    gid = len(groups)
    groups.append({"name": f"export_mask_{gid}", "indices": list(frozen)})
    group_sets.append(frozen)
    group_set_to_id[frozen] = gid
    return gid


def layer_base_indices(*, tk_id, tref, group_sets, zones, num_leds):
    if tk_id == 0:
        return set(range(num_leds))
    if tk_id == 1:
        if 0 <= int(tref) < len(group_sets):
            return set(group_sets[int(tref)])
        return set(range(num_leds))
    if tk_id == 2:
        if 0 <= int(tref) < len(zones):
            zone = zones[int(tref)]
            try:
                start = int(zone.get("start", 0))
                end = int(zone.get("end", 0))
            except Exception:
                return set(range(num_leds))
            if start > end:
                start, end = end, start
            start = 0 if start < 0 else start
            end = (num_leds - 1) if end >= num_leds else end
            return set(range(start, end + 1))
        return set(range(num_leds))
    return set(range(num_leds))


def apply_ui_target_mask(*, ui_mask_set, groups, group_sets, group_set_to_id, zones, num_leds, tk_id, tref):
    if not ui_mask_set:
        return tk_id, tref
    base = layer_base_indices(tk_id=tk_id, tref=tref, group_sets=group_sets, zones=zones, num_leds=num_leds)
    intersected = set(base) & set(ui_mask_set)
    if intersected != base:
        gid = ensure_group_for_indices(
            groups=groups,
            group_sets=group_sets,
            group_set_to_id=group_set_to_id,
            num_leds=num_leds,
            indices=intersected,
        )
        if gid >= 0:
            return 1, gid
    return tk_id, tref
