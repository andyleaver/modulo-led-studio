from runtime.resolver_write import set_address
from runtime.resolver_read import resolve_project_surface_field
from runtime.spatial import surface_snapshot


def test_surface_kind_write_keeps_only_canonical_fields():
    project = {
        "surface": {
            "kind": "strip",
            "shape": "strip",
            "count": 10,
            "mapping": {"serpentine": False},
            "serpentine": False,
        }
    }
    project, changed = set_address(project=project, address="project.surface.kind", value="cells")
    assert changed is True
    surface = project.get("surface") or {}
    assert surface.get("kind") == "cells"
    assert "shape" not in surface
    assert "serpentine" not in surface


def test_surface_mapping_write_keeps_nested_mapping_only():
    project = {
        "surface": {
            "kind": "strip",
            "count": 10,
            "mapping": {"serpentine": False},
            "serpentine": False,
        }
    }
    project, changed = set_address(project=project, address="project.surface.mapping.serpentine", value=True)
    assert changed is True
    surface = project.get("surface") or {}
    assert (surface.get("mapping") or {}).get("serpentine") is True
    assert "serpentine" not in surface


def test_surface_shape_is_not_a_writable_canonical_address():
    project = {"surface": {"kind": "strip", "count": 8}}
    project2, changed = set_address(project=project, address="project.surface.shape", value="cells")
    assert changed is False
    assert project2 == project


def test_surface_snapshot_no_longer_emits_shape_mirror():
    snap = surface_snapshot({"kind": "cells", "width": 4, "height": 2})
    assert snap.get("kind") == "cells"
    assert "shape" not in snap


def test_resolver_read_kind_still_reports_compat_source_from_shape_evidence():
    resolved = resolve_project_surface_field(project={"surface": {"shape": "cells", "width": 4, "height": 2}}, field="kind")
    assert resolved.value == "cells"
    assert resolved.source in {"compat", "project"}

def test_kernel_context_no_longer_exposes_layout_alias():
    from runtime.kernel_context import KernelContext

    ctx = KernelContext(surface={"kind": "strip", "count": 4})
    assert ctx.surface == {"kind": "strip", "count": 4}
    assert "layout" not in vars(ctx)
    assert not hasattr(type(ctx), "layout")



def test_build_surface_dict_no_longer_emits_shape_or_flat_mapping_keys():
    from app.project_model import build_surface_dict

    surface = build_surface_dict(kind='cells', width=4, height=2, mapping={'serpentine': True})
    assert surface.get('kind') == 'cells'
    assert (surface.get('mapping') or {}).get('serpentine') is True
    assert 'shape' not in surface
    assert 'serpentine' not in surface


def test_shape_strip_fallback_does_not_override_cells_geometry():
    from core.surface_compat import get_surface_kind_value

    surface = {'shape': 'strip', 'width': 8, 'height': 8}
    assert get_surface_kind_value(surface, default='strip') == 'cells'


def test_build_surface_geometry_dict_no_longer_emits_compat_mirrors():
    from core.surface_compat import build_surface_geometry_dict

    surface = build_surface_geometry_dict({"shape": "cells", "width": 4, "height": 2, "serpentine": True})
    assert surface.get("kind") == "cells"
    assert (surface.get("mapping") or {}).get("serpentine") is True
    assert "shape" not in surface
    assert "serpentine" not in surface


def test_resolver_height_from_shape_only_reports_compat_source():
    resolved = resolve_project_surface_field(project={"surface": {"shape": "strip"}}, field="height")
    assert resolved.value == 1
    assert resolved.source == "compat"


def test_leaked_root_layout_does_not_drive_resolver_surface_reads():
    project = {"layout": {"shape": "cells", "width": 8, "height": 8, "serpentine": True}}

    kind = resolve_project_surface_field(project=project, field="kind")
    width = resolve_project_surface_field(project=project, field="width")
    mapping = resolve_project_surface_field(project=project, field="mapping")

    assert kind.value == "strip"
    assert kind.source == "default"
    assert width.value == 144
    assert width.source == "default"
    assert mapping.value.get("serpentine") is False
    assert mapping.source == "default"


def test_surface_snapshot_ignores_leaked_root_layout_residue():
    from app.project_model import get_surface_snapshot

    project = {
        "surface": {"kind": "strip", "count": 16, "mapping": {"serpentine": False}},
        "layout": {"shape": "cells", "width": 99, "height": 99, "serpentine": True},
    }

    snap = get_surface_snapshot(project)
    assert snap.get("kind") == "strip"
    assert snap.get("count") == 16
    assert snap.get("width") == 16
    assert snap.get("height") == 1
    assert (snap.get("mapping") or {}).get("serpentine") is False


def test_resolver_read_kind_reports_project_source_from_canonical_geometry_evidence_only():
    resolved = resolve_project_surface_field(project={"surface": {"width": 8, "height": 8}}, field="kind")
    assert resolved.value == "cells"
    assert resolved.source == "project"


def test_apply_surface_compat_mirrors_no_longer_reintroduces_flat_mapping_keys():
    from core.surface_compat import apply_surface_compat_mirrors

    surface = apply_surface_compat_mirrors({"shape": "cells", "width": 4, "height": 2, "serpentine": True})

    assert surface["kind"] == "cells"
    assert "shape" not in surface
    assert "serpentine" not in surface
    assert surface["mapping"]["serpentine"] is True


def test_show_ir_exposes_surface_only_no_layout_alias():
    from export.ir import ShowIR

    ir = ShowIR.from_project(project={}, selection={}, hw={}, audio_hw={})

    assert hasattr(ir, "surface")
    assert not hasattr(ir, "layout")


def test_surface_spec_from_object_ignores_legacy_shape_and_flat_mapping_mirrors():
    from core.surface_spec import surface_spec_from_layout

    class LegacyLikeSurface:
        shape = "strip"
        width = 8
        height = 8
        serpentine = True
        mapping = None

    spec = surface_spec_from_layout(LegacyLikeSurface())

    assert spec.kind == "cells"
    assert spec.width == 8
    assert spec.height == 8
    assert spec.mapping["serpentine"] is False


def test_surface_spec_from_object_uses_canonical_nested_mapping_only():
    from core.surface_spec import surface_spec_from_layout

    class CanonicalSurface:
        kind = "cells"
        width = 4
        height = 2
        mapping = {"serpentine": True, "flip_x": True}

    spec = surface_spec_from_layout(CanonicalSurface())

    assert spec.kind == "cells"
    assert spec.width == 4
    assert spec.height == 2
    assert spec.mapping["serpentine"] is True
    assert spec.mapping["flip_x"] is True


def test_effect_context_exposes_surface_only_no_layout_alias():
    from behaviors.state import EffectContext

    ctx = EffectContext(surface={"kind": "strip", "count": 4})
    assert ctx.surface == {"kind": "strip", "count": 4}
    assert "layout" not in vars(ctx)
    assert not hasattr(type(ctx), "layout")


def test_preview_behavior_injection_exposes_surface_only_no_layout_alias():
    from preview.preview_engine_support import _call_preview_emit

    seen = {}

    class DummyBehavior:
        @staticmethod
        def preview_emit(**kwargs):
            seen.update(kwargs)
            return [(0, 0, 0)] * int(kwargs.get("num_leds", 0))

    out = _call_preview_emit(
        DummyBehavior(),
        num_leds=3,
        params={},
        t=0.0,
        dt=1.0 / 60.0,
        state={},
        surface={"kind": "strip", "count": 3},
        audio={},
    )

    assert len(out) == 3
    assert seen["surface"] == {"kind": "strip", "count": 3}
    assert "layout" not in seen
