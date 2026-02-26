"""Behaviors.effects package.

IMPORTANT:
- We do NOT auto-import every .py module in this folder.
  Auto-import scanning caused fragile imports for experimental demos.
- Shipped effects are registered explicitly via behaviors.auto_load.register_all().
"""
from __future__ import annotations

from behaviors.auto_load import register_all

# Register shipped effects only
register_all()
