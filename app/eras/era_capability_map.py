from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

from behaviors.registry import list_effect_keys
from export.export_eligibility import get_eligibility, ExportStatus


@dataclass(frozen=True)
class CapabilityMap:
    total_behaviors: int
    exportable: int
    preview_only: int
    blocked: int
    blocked_examples: List[Tuple[str, str]]
    preview_examples: List[Tuple[str, str]]

    def to_text(self) -> str:
        lines: List[str] = []
        lines.append("ERA 6 — MODULO: CODE-DERIVED CAPABILITY MAP")
        lines.append("")
        lines.append(f"Behaviors registered (code): {self.total_behaviors}")
        lines.append(f"Exportable: {self.exportable}")
        lines.append(f"Preview-only: {self.preview_only}")
        lines.append(f"Blocked: {self.blocked}")
        lines.append("")
        if self.blocked_examples:
            lines.append("Blocked examples:")
            for k, reason in self.blocked_examples[:10]:
                lines.append(f"  - {k}: {reason}")
            lines.append("")
        if self.preview_examples:
            lines.append("Preview-only examples:")
            for k, reason in self.preview_examples[:10]:
                lines.append(f"  - {k}: {reason}")
            lines.append("")
        lines.append("Note: This output is generated from registry + export eligibility in code (not README).")
        return "\n".join(lines)


def compute_capability_map() -> CapabilityMap:
    keys = list_effect_keys()
    exportable = 0
    preview_only = 0
    blocked = 0
    blocked_examples: List[Tuple[str, str]] = []
    preview_examples: List[Tuple[str, str]] = []

    for k in keys:
        elig = get_eligibility(k)
        if elig.status == ExportStatus.EXPORTABLE:
            exportable += 1
        elif elig.status == ExportStatus.BLOCKED:
            blocked += 1
            blocked_examples.append((k, elig.reason))
        else:
            preview_only += 1
            preview_examples.append((k, elig.reason))

    # deterministic: sort examples by key
    blocked_examples.sort(key=lambda x: x[0])
    preview_examples.sort(key=lambda x: x[0])

    return CapabilityMap(
        total_behaviors=len(keys),
        exportable=exportable,
        preview_only=preview_only,
        blocked=blocked,
        blocked_examples=blocked_examples,
        preview_examples=preview_examples,
    )


def compute_capability_map_text_full() -> str:
    """Return a full, code-derived listing of behaviors and their export status.

    This is intentionally generated from executable code paths (registry + export eligibility),
    not from README text.
    """
    keys = list_effect_keys()
    exportable_keys: List[str] = []
    blocked_items: List[Tuple[str, str]] = []
    preview_items: List[Tuple[str, str]] = []

    for k in keys:
        elig = get_eligibility(k)
        if elig.status == ExportStatus.EXPORTABLE:
            exportable_keys.append(k)
        elif elig.status == ExportStatus.BLOCKED:
            blocked_items.append((k, elig.reason))
        else:
            preview_items.append((k, elig.reason))

    exportable_keys.sort()
    blocked_items.sort(key=lambda x: x[0])
    preview_items.sort(key=lambda x: x[0])

    lines: List[str] = []
    lines.append("ERA 6 — MODULO: WHAT IS POSSIBLE NOW (FROM CODE)")
    lines.append("(Generated from behavior registry + export eligibility; not README.)")
    lines.append("")
    lines.append(f"Total behaviors registered: {len(keys)}")
    lines.append(f"Exportable: {len(exportable_keys)}")
    lines.append(f"Preview-only: {len(preview_items)}")
    lines.append(f"Blocked: {len(blocked_items)}")
    lines.append("")

    lines.append(f"Exportable behaviors ({len(exportable_keys)}):")
    for k in exportable_keys:
        lines.append(f"  - {k}")
    lines.append("")

    lines.append(f"Preview-only behaviors ({len(preview_items)}):")
    for k, reason in preview_items:
        lines.append(f"  - {k} — {reason}")
    lines.append("")

    lines.append(f"Blocked behaviors ({len(blocked_items)}):")
    for k, reason in blocked_items:
        lines.append(f"  - {k} — {reason}")

    return "\n".join(lines)
