from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class EraGates:
    # Hard gates (UI + registry filtering)
    allowed_effects: Optional[List[str]] = None  # None => no filter
    max_layers: int = 99
    allow_operators: bool = True
    allow_rules: bool = True
    allow_audio: bool = True
    allow_targets: bool = True
    allow_export: bool = True
    allow_matrix: bool = True


@dataclass(frozen=True)
class Era:
    era_id: str
    title: str
    start_year: int
    key_person: str
    summary: str
    what_was_possible: List[str] = field(default_factory=list)
    gates: EraGates = field(default_factory=EraGates)


def get_eras() -> List[Era]:
    # Era 1: 1962 — Visible red LED enters practical use
    era1 = Era(
        era_id="era_1962_red",
        title="1962 — Red LED (indicator)",
        start_year=1962,
        key_person="Nick Holonyak Jr.",
        summary=(
            "The first practical visible-spectrum LED (red). "
            "A single indicator light that can be switched, dimmed, and pulsed."
        ),
        what_was_possible=[
            "Single red indicator light",
            "On/off switching",
            "Brightness control (dimming)",
            "Pulsing / simple signalling",
        ],
        gates=EraGates(
            allowed_effects=["solid_red_1962"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
        ),
    )

    # Era 2: 1972 — New colours reach practicality (yellow milestone; multi-colour signalling culture)
    era2 = Era(
        era_id="era_1972_yellow_green",
        title="1972 — Yellow LED & multi-colour indicators",
        start_year=1972,
        key_person="M. George Craford",
        summary=(
            "More visible signalling colours reach practical use in real products. "
            "Multi-state colour signalling becomes a familiar pattern."
        ),
        what_was_possible=[
            "Red / yellow / green indicator signalling",
            "Simple multi-state feedback using colour",
            "Pulse signalling",
            "Dimming on indicators",
        ],
        gates=EraGates(
            allowed_effects=["solid_red_1962", "solid_yellow_1972", "solid_green_era"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
        ),
    )

    # Era 3: 1980s — High-brightness status/alert culture
    era3 = Era(
        era_id="era_1980s_high_brightness",
        title="1980s — High-brightness alerts",
        start_year=1980,
        key_person="—",
        summary=(
            "High-brightness LEDs drive clearer status lights and attention signals. "
            "Fast pulsing becomes a common 'alert' language."
        ),
        what_was_possible=[
            "High-visibility indicator lights",
            "Fast / slow pulse signalling",
            "Clear brightness contrast for alerts",
        ],
        gates=EraGates(
            allowed_effects=["solid_red_1962", "solid_yellow_1972", "solid_green_era"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
        ),
    )

    # Era 4: 1993 — Blue breakthrough enables practical full-colour mixing trajectories
    era4 = Era(
        era_id="era_1993_blue",
        title="1993 — Blue LED breakthrough",
        start_year=1993,
        key_person="Akasaki / Amano / Nakamura",
        summary=(
            "Efficient blue LEDs enable the path to practical full-colour mixing and white light products."
        ),
        what_was_possible=[
            "Practical blue indicator output",
            "RGB mixing becomes viable in products",
            "Mixed light can produce WHITE",
        ],
        gates=EraGates(
            allowed_effects=["solid_rgb_mix"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
        ),
    )

    # Era 5: 1996 — White LED becomes practical for illumination
    era5 = Era(
        era_id="era_1996_white",
        title="1996 — White LED (illumination)",
        start_year=1996,
        key_person="—",
        summary=(
            "White LEDs become practical for illumination and general-purpose lighting products."
        ),
        what_was_possible=[
            "Practical white light output",
            "Discrete white 'types' as product choices",
            "Dimming scenes (lamp behaviour)",
        ],
        gates=EraGates(
            allowed_effects=["solid_white_1996"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=False,
        ),
    )

    # Era 6: 2000s — Matrices and 2D signage behaviours
    era6 = Era(
        era_id="era_2000s_matrices",
        title="2000s — LED matrices (2D grids)",
        start_year=2000,
        key_person="—",
        summary=(
            "2D pixel grids become common in signage and displays. Position and motion on a grid matters."
        ),
        what_was_possible=[
            "2D pixel grids",
            "Coordinate-based patterns",
            "Scrolling / motion on a grid",
        ],
        gates=EraGates(
            allowed_effects=["matrix_dot", "matrix_scroll_bar"],
            max_layers=1,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=False,
            allow_export=False,
            allow_matrix=True,
        ),
    )

    # Era 7: 2012 — Addressable pixels (per-pixel RGB)
    era7 = Era(
        era_id="era_2012_addressable",
        title="2012 — Addressable pixels",
        start_year=2012,
        key_person="—",
        summary=(
            "Per-pixel control (RGB by index) becomes mainstream for strips, rings, and small installations."
        ),
        what_was_possible=[
            "Per-pixel RGB control",
            "Index-based animations (chase, wipes)",
            "Real-time patterns on strips/rings",
        ],
        gates=EraGates(
            allowed_effects=["chase", "color_wipe", "theater_chase", "wipe"],
            max_layers=2,
            allow_operators=False,
            allow_rules=False,
            allow_audio=False,
            allow_targets=True,
            allow_export=True,
            allow_matrix=True,
        ),
    )

    # History entry (not a capability era): a pause in how LEDs were used
    plateau = Era(
        era_id="era_usage_plateau",
        title="A pause in how LEDs were used",
        start_year=2010,
        key_person="—",
        summary=(
            "As LEDs became more capable, control software often converged on preset animations and effect selection."
        ),
        what_was_possible=[
            "Hardware advanced (addressability, matrices, brightness, colour fidelity)",
            "Tooling/UI converged on preset animations",
            "Dominant model: choose an effect, tweak a few parameters, repeat",
            "This was a tooling/mental-model plateau, not a hardware limit",
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
        ),
    )

    # Final panel (not an era): Now — what Modulo enables today
    now = Era(
        era_id="era_now",
        title="Now",
        start_year=2026,
        key_person="—",
        summary=(
            "This is not an era defined by Modulo. Modulo does not claim what this era is. "
            "What comes next is defined by what you create."
        ),
        what_was_possible=[
            "What Modulo enables today (audited, code-truth):",
            "Layered composition",
            "Stateful behaviour (tick → update → render)",
            "Rules and signals (where supported)",
            "Strips + matrices with deterministic mapping",
            "Sprites, tilemaps, and world abstractions",
            "Diagnostics, audits, and validation",
            "Firmware export to real targets (with clear blockers where unsupported)",
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
        ),
    )

    return [era1, era2, era3, era4, era5, era6, era7, plateau, now]


def get_era(era_id: str) -> Era:
    for e in get_eras():
        if e.era_id == era_id:
            return e
    return get_eras()[0]


def get_default_era_id() -> str:
    # Default to first historical era
    return get_eras()[0].era_id
