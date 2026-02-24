from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .life_snake import build_life_snake_project
from .brain_life_ant import build_brain_life_ant_project
from .breakout_invaders import build_breakout_invaders_project
from .red_hat_runner import build_red_hat_runner_project


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
]


def get_showcases() -> List[Showcase]:
    return list(SHOWCASES)
