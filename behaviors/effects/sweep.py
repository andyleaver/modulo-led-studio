from __future__ import annotations
SHIPPED = True

"""sweep: shipped effect module wrapper.

The implementation lives in behaviors/effects/scanner.py (shared code). This
wrapper exists so tooling (validate_behaviors) can map shipped keys to modules
1:1 without forcing code duplication.
"""

from behaviors.effects.scanner import register_sweep

__all__ = ["register_sweep"]
