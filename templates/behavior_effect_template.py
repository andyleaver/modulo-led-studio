"""Effect template.

1) Copy this file to behaviors/effects/<your_effect_key>.py
2) Implement render() deterministically (seeded RNG only).
3) Register it in behaviors/auto_load.py via register_effect("<your_effect_key>")
4) Add your effect to behaviors/capabilities_catalog.json under effects{}
5) Add export eligibility in export/export_eligibility.py
6) Provide a golden fixture in demos/ and add it to tools/golden_exports.py FIXTURES
"""

from behaviors.stateful import StatefulEffect
from params.purpose_contract import PurposeParams

class Effect(StatefulEffect):
    key = "<your_effect_key>"
    title = "<Human Title>"

    def __init__(self, params: PurposeParams):
        super().__init__(params)
        # deterministic internal state here

    def tick(self, dt: float):
        # deterministic update; dt is fixed-step in export runtimes
        pass

    def render(self, fb):
        # fb is logical framebuffer (strip or matrix via mapping)
        # write pixels deterministically
        pass
