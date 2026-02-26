from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .life_snake import build_life_snake_project
from .brain_life_ant import build_brain_life_ant_project
from .breakout_invaders import build_breakout_invaders_project
from .red_hat_runner import build_red_hat_runner_project
from .fsm_phases import build_fsm_phases_project

from .new_era import (
    build_boids_swarm_project,
    build_predator_prey_project,
    build_memory_heatmap_project,
    build_ambient_dashboard_project,
    build_agents_memory_narrative_project,
)


@dataclass(frozen=True)
class Showcase:
    id: str
    title: str
    subtitle: str
    builder: Callable[[], dict]
    steps: List[str]


SHOWCASES: List[Showcase] = [    Showcase(
        id="life_snake",
        title="Life + Snake",
        subtitle="Two evolving systems layered together",
        builder=build_life_snake_project,
        steps=[
            "This scene is built from two independent systems evolving over time.",
            "Layer 1: Game of Life. It updates based on neighbor cells each step.",
            "Layer 2: Snake (INO). It has memory and grows as it eats food.",
            "Layer order + visibility: this showcase uses opacity + blend so you can see both at once.",
        ],
    ),
    Showcase(
        id="brain_life_ant",
        title="Brain + Life + Ant",
        subtitle="Three independent systems sharing one space (24×24)",
        builder=build_brain_life_ant_project,
        steps=[
            "This scene layers three independent simulations: Brian’s Brain (waves), Game of Life (structure), and Langton’s Ant (an agent).",
            "Brian’s Brain is subtle (opacity ~0.25) to act like a moving energy field behind everything.",
            "Life adds evolving structure (opacity ~0.35). The Ant sits on top with Add blend so it stays clearly visible.",
            "Try this: tweak speed/density on one layer, or temporarily disable a layer. Notice the others keep evolving independently.",
        ],
    ),
    Showcase(
        id="breakout_invaders",
        title="Breakout + Invaders",
        subtitle="Only after bricks clear: the ball can destroy invaders",
        builder=build_breakout_invaders_project,
        steps=[
            "Two games run as separate layers in the same 24×24 world.",
            "Breakout behaves normally until all bricks are cleared.",
            "Only after bricks clear, the ball becomes 'free' briefly and can destroy invaders by touching them.",
            "This uses an engine-owned interaction bus: layers don’t import or depend on each other.",
        ],
    ),
    Showcase(
        id="red_hat_runner",
        title="Red Hat Runner",
        subtitle="State + rules: jump on events",
        builder=build_red_hat_runner_project,
        steps=[
            "This example is driven by state, not a static animation.",
            "A rules_v6 trigger sets jump_now when the minute changes.",
            "The layer responds by transitioning run → jump → run.",
            "Tweak gravity/jump_v, or wire another trigger (audio threshold) to jump_now.",
        ],
    ),


    Showcase(
        id="fsm_phases",
        title="Narrative Phases (FSM)",
        subtitle="Shared state machine with phase progression",
        builder=build_fsm_phases_project,
        steps=[
            "This showcase uses fsm_v1 to progress through phases over time.",
            "It is implemented via write_the_loop so preview and export match.",
            "Phase 1: calm gradient → Phase 2: pulse bars → Phase 3: sparkle storm.",
            "Use purpose_f0 to control overall brightness.",
        ],
    ),
    Showcase(
        id="boids_swarm",
        title="Boids Swarm",
        subtitle="Emergent motion from local rules",
        builder=build_boids_swarm_project,
        steps=[
            "This is a behavior system: each boid reacts only to neighbors.",
            "Try changing boids_count, boids_sep, boids_align, boids_cohesion.",
            "Notice it still looks alive even when slowed down.",
        ],
    ),
    Showcase(
        id="predator_prey",
        title="Predator / Prey",
        subtitle="A tiny world: chase, flee, respawn",
        builder=build_predator_prey_project,
        steps=[
            "Two agents share one space: prey wanders, predator chases.",
            "When the predator catches the prey, the prey respawns and score increments.",
            "This is an example of LEDs as a world, not a pattern.",
        ],
    ),

Showcase(
    id="agents_memory_narrative",
    title="Agents + Memory + Narrative",
    subtitle="Boids carve motion into long memory; phases tint the scene",
    builder=build_agents_memory_narrative_project,
    steps=[
        "This is a composite behavior scene: agents (boids) + long-memory heat + a narrative overlay.",
        "Memory Heatmap persists and decays over time (long_memory_v1).",
        "Boids run on agents_v1 (shared agent framework).",
        "Narrative overlay uses fsm_v1 via the FSM Phases layer.",
        "Note: this showcase is preview-first until long-memory export wiring for this composite is finalized.",
    ],
),

    Showcase(
        id="memory_heatmap",
        title="Memory Heatmap",
        subtitle="Persistent field that stores events",
        builder=build_memory_heatmap_project,
        steps=[
            "This layer accumulates 'events' over time and slowly decays.",
            "It's useful as a background memory for other layers.",
            "Try lowering mem_decay for shorter memory, or raising mem_inject for more intensity.",
        ],
    ),
    Showcase(
        id="ambient_dashboard",
        title="Ambient Dashboard",
        subtitle="LEDs as an information surface",
        builder=build_ambient_dashboard_project,
        steps=[
            "This is a use-case example: an ambient status wall.",
            "It synthesizes stable signals (mood gradient + indicators).",
            "If audio is enabled, energy can boost the alert indicator.",
        ],
    ),
]


def get_showcases() -> List[Showcase]:
    return list(SHOWCASES)
