from core.surface_compat import build_surface_geometry_dict, get_surface_mapping_values
def _get_surface_spec(project):
    from app.project_model import get_surface_spec
    return get_surface_spec(project)

# Exporters should consume SurfaceSpec via:
#   from app.project_model import get_surface_spec
#   spec = get_surface_spec(project)
# This prevents preview/export geometry divergence.
# ------------------------------------------------------------------
# Exporter now reads canonical SurfaceSpec (preview/export parity anchor)
# ------------------------------------------------------------------
def _surface_spec_debug(project):
    spec = _get_surface_spec(project)
    if spec:
        return spec.summary()
    return {"error": "No SurfaceSpec available"}

# ------------------------------------------------------------------
# Exporter geometry now enforced via SurfaceSpec
# ------------------------------------------------------------------
def _get_geometry_from_surface(project):
    spec = _get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export aborted (parity enforcement).")
    mapping = get_surface_mapping_values(spec)
    return spec.width, spec.height, spec.count, bool(mapping.get("serpentine", False))

# ------------------------------------------------------------------
# All exporters must use SurfaceSpec for geometry truth
# ------------------------------------------------------------------
def _surface_geometry(project):
    spec = _get_surface_spec(project) if "_get_surface_spec" in globals() else get_surface_spec(project)
    if not spec:
        raise RuntimeError("SurfaceSpec missing — export blocked.")
    return build_surface_geometry_dict(spec, default_kind="strip", default_count=60)


# ------------------------------------------------------------------
# Legacy layout-based geometry access is deprecated.
# Exporters must NOT read project.surface.shape/width/height directly.
# Geometry authority = SurfaceSpec via get_surface_spec().
# ------------------------------------------------------------------

def get_export_frame_buffer(project):
    # Replace with real exporter frame generation hook
    return []
