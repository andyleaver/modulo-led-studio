"""Export preconditions.

This module contains lightweight checks that must pass before generating a sketch.
It is intentionally dependency-free and lives under export/ so runtime never imports tools/.
"""

from __future__ import annotations

from typing import Any, List, Tuple


def check(project: dict) -> Tuple[bool, List[str], List[str]]:
    """Return (ok, problems, warnings).

    Keep this conservative and schema-tolerant:
    - Fail only on conditions that would definitely make export invalid.
    - Everything else is a warning (or handled by deeper validation in the exporter).
    """
    problems: List[str] = []
    warns: List[str] = []

    if not isinstance(project, dict):
        return False, ["Project is not a dict."], []

    layout = project.get("layout") or {}
    if not isinstance(layout, dict):
        problems.append("layout must be an object.")
        return False, problems, warns

    kind = str(layout.get("kind") or layout.get("shape") or layout.get("type") or "").strip().lower()
    if kind not in ("strip", "matrix", "cells"):
        problems.append("layout.kind must be one of: strip, matrix, cells.")
    else:
        # Require a positive LED count for strip/cells; matrix is validated later via export.hw.matrix.
        if kind in ("strip", "cells"):
            n = layout.get("num_leds")
            try:
                n_int = int(n)
            except Exception:
                n_int = None
            if n_int is None or n_int <= 0:
                problems.append("layout.num_leds must be a positive integer.")

    layers = project.get("layers")
    if layers is None:
        warns.append("No layers present (layers missing). Export will generate an empty sketch.")
    elif not isinstance(layers, list):
        problems.append("layers must be a list.")

    return (len(problems) == 0), problems, warns
