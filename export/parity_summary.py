from .parity_summary_core import (
    ParitySummary,
    _as_int,
    _norm_pin,
    compute_export_parity_summary,
    _find_target_meta,
    build_parity_summary,
)
from .parity_summary_format import (
    layer_parity,
    layer_tag_text,
    summarize_layers,
    format_project_badge,
    format_export_report_line,
    format_export_block_message,
    _surface_geometry,
)

__all__ = [
    "ParitySummary",
    "_as_int",
    "_norm_pin",
    "compute_export_parity_summary",
    "_find_target_meta",
    "build_parity_summary",
    "layer_parity",
    "layer_tag_text",
    "summarize_layers",
    "format_project_badge",
    "format_export_report_line",
    "format_export_block_message",
    "_surface_geometry",
]
