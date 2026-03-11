from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class EraWorkbench:
    goal: str
    verify_steps: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class EraGates:
    allowed_effects: Optional[List[str]] = None
    max_layers: int = 99
    allow_operators: bool = True
    allow_rules: bool = True
    allow_audio: bool = True
    allow_targets: bool = True
    allow_export: bool = True
    allow_matrix: bool = True
    allow_addressable: bool = True
    allow_presets: bool = True
    allow_full_modulo: bool = True
    control_model: str = "full_modulo"
    phase_kind: str = "modulo"
    stop_here_ok: bool = False
    control_capabilities: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class Era:
    era_id: str
    title: str
    start_year: int
    key_person: str
    summary: str
    what_was_possible: List[str] = field(default_factory=list)
    gates: EraGates = field(default_factory=EraGates)
    workbench: Optional[EraWorkbench] = None

ERAS: List[Era] = [
    Era(
        era_id="era_1962_red",
        title="1962 — First Practical Visible LED",
        start_year=1962,
        key_person="Nick Holonyak Jr.",
        summary="With Nick Holonyak Jr.’s practical visible red LED in 1962, LED control begins as a single visible indicator. A user can switch one lamp on or off and use simple pulse signalling.",
        what_was_possible=[
            "Single visible indicator light",
            "On / off control",
            "Simple pulse signalling",
        ],
        workbench=EraWorkbench(
            goal="Bring a single red indicator to life, then prove it can signal by pulsing.",
            verify_steps=[
                "Turn the LED on.",
                "Switch the indicator from steady output to pulse.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["solid_red_1962"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="indicator",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["single_led", "on_off", "pulse_signal"],
        ),
    ),
    Era(
        era_id="era_1972_yellow_green",
        title="1972 — Brighter Red + Yellow Indicators",
        start_year=1972,
        key_person="M. George Craford",
        summary="In 1972, M. George Craford introduced the first yellow LED and a much brighter red LED. Indicator control expands into clearer practical status signalling while still controlling one point at a time.",
        what_was_possible=[
            "Brighter red indicator states",
            "Yellow indicator states",
            "Simple multi-state status signalling",
            "Pulse signalling",
        ],
        workbench=EraWorkbench(
            goal="Use brighter red and yellow as status states, then pulse one of them.",
            verify_steps=[
                "Turn the indicator on.",
                "Select red and yellow status states.",
                "Use pulse signalling at least once.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["solid_red_1962", "solid_yellow_1972"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="indicator_colour",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["single_led", "yellow_status", "brighter_red", "pulse_signal"],
        ),
    ),
    Era(
        era_id="era_1980s_high_brightness",
        title="1980s — Programmed Alert Patterns",
        start_year=1980,
        key_person="Programmable display / control era",
        summary="LED control moves into timed behaviour. Users can create simple alert patterns such as flashing and programmed cadence instead of only static state lamps.",
        what_was_possible=[
            "Fast / slow pulse patterns",
            "Brightness contrast for status and alerts",
            "Simple timed pattern behaviour",
        ],
        workbench=EraWorkbench(
            goal="Turn a status lamp into an alert lamp using cadence and intensity.",
            verify_steps=[
                "Turn the indicator on.",
                "Switch the pulse rate to FAST.",
                "Change brightness at least once to create contrast.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["solid_red_1962", "solid_yellow_1972", "pulse_red_1980s"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="alert_pattern",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["single_led", "timed_patterns", "brightness_contrast"],
        ),
    ),
    Era(
        era_id="era_1993_blue",
        title="1993 — RGB Colour Mixing",
        start_year=1993,
        key_person="Akasaki / Amano / Nakamura",
        summary="Efficient practical blue LED output in the early 1990s makes intentional RGB mixing truly practical. Users can now mix colour instead of selecting from isolated indicator lamps.",
        what_was_possible=[
            "RGB colour mixing",
            "Colour fades and mixed hues",
            "Single-scene colour selection",
        ],
        workbench=EraWorkbench(
            goal="Mix channels to create a colour that is not just a single red, green, or blue lamp.",
            verify_steps=[
                "Turn the LED on.",
                "Blend at least two RGB channels to make a mixed hue.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["solid_rgb_mix", "fade"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="rgb_mix",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["rgb_mix", "colour_fade", "scene_colour"],
        ),
    ),
    Era(
        era_id="era_1996_white",
        title="1996 — White LED Lighting",
        start_year=1996,
        key_person="Nichia phosphor white LED",
        summary="With phosphor-converted white LEDs in 1996, LED control behaves more like lighting. Users can work with white-light scenes and dimming rather than only indicator colours.",
        what_was_possible=[
            "White light output",
            "Lamp-style dimming scenes",
            "Warm / cool product-style white choices",
        ],
        workbench=EraWorkbench(
            goal="Treat the LED as lighting: pick a white tone, then dim it like a lamp.",
            verify_steps=[
                "Turn the lamp on.",
                "Change the white type at least once.",
                "Dim the light at least once.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["solid_white_1996"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="white_lighting",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["white_scene", "dimming", "lighting_use"],
        ),
    ),
    Era(
        era_id="era_2000s_matrices",
        title="2000s — Programmable LED Arrays",
        start_year=2000,
        key_person="DIY microcontroller display era",
        summary="Position starts to matter. Users can treat LEDs as strips or simple arrays with moving dots, scrolling, and coordinate-based graphics.",
        what_was_possible=[
            "1D / 2D LED arrays",
            "Coordinate-based motion",
            "Scrolling and moving dots",
        ],
        workbench=EraWorkbench(
            goal="Prove that position now matters by moving a pixel through an array and triggering motion across it.",
            verify_steps=[
                "Turn the array on.",
                "Move the dot to a new coordinate.",
                "Trigger scrolling or motion across the array.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["matrix_dot", "matrix_scroll_bar", "clock_seconds_dot"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=True,
            allow_addressable=False,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="array_control",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["array_layout", "coordinate_motion", "scrolling"],
        ),
    ),
    Era(
        era_id="era_2012_addressable",
        title="2012 — Addressable Pixels",
        start_year=2012,
        key_person="Integrated digital pixel era",
        summary="Per-pixel control becomes practical. Users can animate each LED directly in strips, rings, and small matrices.",
        what_was_possible=[
            "Per-pixel RGB control",
            "Index-based animations",
            "Small programmable LED installations",
        ],
        workbench=EraWorkbench(
            goal="Control one pixel by address, then show that animation and colour can change independently.",
            verify_steps=[
                "Turn the strip on.",
                "Move the active pixel to a different index.",
                "Change the motion mode.",
                "Change colour while it is addressable.",
            ],
        ),
        gates=EraGates(
            allowed_effects=["chase", "color_wipe", "theater_chase", "wipe"],
            max_layers=2,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=True,
            allow_export=True,
            allow_matrix=True,
            allow_addressable=True,
            allow_presets=False,
            allow_full_modulo=False,
            control_model="addressable_pixels",
            phase_kind="historical",
            stop_here_ok=False,
            control_capabilities=["per_pixel", "index_animation", "small_installation"],
        ),
    ),
    Era(
        era_id="era_usage_plateau",
        title="2010s — Modern LED App / Effect Picker",
        start_year=2010,
        key_person="Consumer LED app paradigm",
        summary="This is the familiar modern LED app model that spread through the 2010s: choose an effect, tweak a few settings, and run it. Users can stay here and work in the conventional effect-picker model.",
        what_was_possible=[
            "Preset effect selection",
            "Brightness / speed / colour tweaking",
            "Practical consumer LED-strip workflow",
        ],
        gates=EraGates(
            allowed_effects=None,
            max_layers=8,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=True,
            allow_export=True,
            allow_matrix=True,
            allow_addressable=True,
            allow_presets=True,
            allow_full_modulo=False,
            control_model="effect_picker",
            phase_kind="plateau",
            stop_here_ok=True,
            control_capabilities=["preset_effects", "effect_tweaks", "consumer_workflow"],
        ),
    ),
    Era(
        era_id="era_now",
        title="Modulo — Full LED Control",
        start_year=2026,
        key_person="Modulo",
        summary="This is where Modulo itself appears. LED control becomes first-class and fully routable with layers, rules, signals, systems, export, diagnostics, and escape hatches for user code when deeper control is needed.",
        what_was_possible=[
            "Layered composition",
            "Rules and signals",
            "Operators and routed parameters",
            "System and world behaviours",
            "Full diagnostics and export",
            "Escape hatches for user code",
        ],
        gates=EraGates(
            allowed_effects=None,
            max_layers=99,
            allow_operators=True,
            allow_rules=True,
            allow_audio=True,
            allow_targets=True,
            allow_export=True,
            allow_matrix=True,
            allow_addressable=True,
            allow_presets=True,
            allow_full_modulo=True,
            control_model="full_modulo",
            phase_kind="modulo",
            stop_here_ok=True,
            control_capabilities=["layers", "rules", "signals", "operators", "systems", "export", "diagnostics", "full_routing"],
        ),
    ),
]
