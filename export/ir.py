from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ShowIR:
    """
    Target-neutral intermediate representation (bootstrap).

    For now it holds:
      - the validated project dict
      - resolved selection/hw/audio_hw
      - convenience fields for layout/layers
    """
    project: Dict[str, Any]
    selection: Dict[str, Any]
    hw: Dict[str, Any]
    audio_hw: Dict[str, Any]
    layout: Dict[str, Any]
    layers: List[Dict[str, Any]]

    @staticmethod
    def from_project(project: Dict[str, Any], selection: Dict[str, Any], hw: Dict[str, Any], audio_hw: Dict[str, Any]) -> "ShowIR":
        project = project or {}
        return ShowIR(
            project=project,
            selection=selection or {},
            hw=hw or {},
            audio_hw=audio_hw or {},
            layout=(project.get("layout") or {}),
            layers=list(project.get("layers") or []),
        )
