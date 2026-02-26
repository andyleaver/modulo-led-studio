from __future__ import annotations

"""Health probe for LongMemory primitives.

We intentionally keep this lightweight: it reports availability and basic defaults.
Actual memory instances live inside behaviors (state), so they are not globally enumerable.
"""

from runtime.extensions_v1 import register_health_probe


def _probe():
    return {
        'available': True,
        'module': 'runtime.long_memory_v1',
        'notes': 'Long-memory buffers (decay + reinforcement). Persistence is Phase 2.',
    }


register_health_probe('long_memory', _probe)
