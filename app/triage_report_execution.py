from __future__ import annotations

"""Canonical triage summary execution surfaces."""

from typing import List

Status = str

TRIAGE_ADDRESS_MATRIX: List[str] = [
    "project.surface.kind",
    "project.surface.count",
    "project.surface.width",
    "project.surface.height",
    "project.surface.mapping.serpentine",
    "project.postfx.trail_amount",
    "project.postfx.bleed_amount",
    "project.postfx.bleed_radius",
    "project.spatial.enabled",
    "project.spatial.world_scale",
]

from app.triage_report_build import *
from app.triage_report_metrics import *
from app.triage_report_debt import *
from app.triage_report_delta import *
