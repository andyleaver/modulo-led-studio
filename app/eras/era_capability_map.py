from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .era_history import get_eras, get_phase_note, get_studio_tools_for_era

@dataclass(frozen=True)
class CapabilityRow:
    era_id: str
    title: str
    control_model: str
    phase_kind: str
    user_control: str
    control_capabilities: List[str]
    studio_tools: List[str]
    matrix: bool
    addressable: bool
    presets: bool
    rules: bool
    operators: bool
    export: bool
    full_modulo: bool
    stop_here_ok: bool

def _user_control_for_model(model: str) -> str:
    return {
        'indicator': 'single indicator control',
        'indicator_colour': 'multi-state indicator control',
        'alert_pattern': 'timed alert pattern control',
        'rgb_mix': 'RGB colour-mixing control',
        'white_lighting': 'white-light dimming control',
        'array_control': 'array and coordinate control',
        'addressable_pixels': 'per-pixel addressable control',
        'effect_picker': 'preset effect picker control',
        'full_modulo': 'fully routed behavioural control',
    }.get(str(model or '').strip().lower(), 'custom control model')

def get_capability_rows() -> List[CapabilityRow]:
    rows: List[CapabilityRow] = []
    for era in get_eras():
        g = era.gates
        rows.append(
            CapabilityRow(
                era_id=era.era_id,
                title=era.title,
                control_model=g.control_model,
                phase_kind=str(getattr(g, 'phase_kind', 'historical') or 'historical'),
                user_control=_user_control_for_model(g.control_model),
                control_capabilities=list(getattr(g, 'control_capabilities', []) or []),
                studio_tools=list(get_studio_tools_for_era(era)),
                matrix=bool(g.allow_matrix),
                addressable=bool(g.allow_addressable),
                presets=bool(g.allow_presets),
                rules=bool(g.allow_rules),
                operators=bool(g.allow_operators),
                export=bool(g.allow_export),
                full_modulo=bool(g.allow_full_modulo),
                stop_here_ok=bool(getattr(g, 'stop_here_ok', False)),
            )
        )
    return rows

def compute_capability_map_text_full() -> str:
    lines: List[str] = ['LED ERA CONTROL CAPABILITY MAP', '']
    current_phase = None
    for row in get_capability_rows():
        if row.phase_kind != current_phase:
            current_phase = row.phase_kind
            lines.append(f"[{current_phase.upper()}]")
        lines.append(f"{row.title} ({row.era_id})")
        lines.append(f"  phase_kind: {row.phase_kind}")
        try:
            era = next((e for e in get_eras() if e.era_id == row.era_id), None)
            if era is not None:
                lines.append(f"  phase_note: {get_phase_note(era)}")
        except Exception:
            pass
        lines.append(f"  control_model: {row.control_model}")
        lines.append(f"  user_control: {row.user_control}")
        lines.append(f"  control_capabilities: {', '.join(row.control_capabilities) if row.control_capabilities else '-'}")
        lines.append(f"  studio_tools: {', '.join(row.studio_tools) if row.studio_tools else '-'}")
        lines.append(f"  matrix: {'yes' if row.matrix else 'no'}")
        lines.append(f"  addressable: {'yes' if row.addressable else 'no'}")
        lines.append(f"  presets: {'yes' if row.presets else 'no'}")
        lines.append(f"  rules: {'yes' if row.rules else 'no'}")
        lines.append(f"  operators: {'yes' if row.operators else 'no'}")
        lines.append(f"  export: {'yes' if row.export else 'no'}")
        lines.append(f"  full_modulo: {'yes' if row.full_modulo else 'no'}")
        lines.append(f"  stop_here_ok: {'yes' if row.stop_here_ok else 'no'}")
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'

def compute_capability_map() -> str:
    return compute_capability_map_text_full()
