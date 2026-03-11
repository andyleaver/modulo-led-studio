from __future__ import annotations

from app.project_canonical import canonicalize_project_dict
from export.arduino_exporter_layerstack_pack import build_layerstack_export_context
from export.arduino_exporter_layerstack_codegen import render_layerstack_sketch


def make_layerstack_sketch(*, project: dict) -> str:
    """Generate an Arduino sketch that renders the canonical layer stack export."""
    project, _canon_changes = canonicalize_project_dict(project or {})
    context = build_layerstack_export_context(project=project)
    return render_layerstack_sketch(context)
