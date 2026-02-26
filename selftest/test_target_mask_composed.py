def test_target_mask_composed_union():
    from preview.preview_engine import PreviewEngine
    from preview.audio import AudioSim
    from models.project_model import ProjectModel

    project = {
        "layout": {"shape": "strip", "num_leds": 10, "count": 10},
        "layers": [
            {"name": "L1", "behavior": "solid", "params": {"color": [255, 0, 0]},
             "opacity": 1.0, "blend_mode": "normal", "target_kind": "all", "target_ref": 0},
        ],
        "masks": {
            "a": {"indices": [0, 1]},
            "b": {"indices": [5, 6]},
            "u": {"op": "union", "a": "a", "b": "b"}
        },
        "ui": {"target_mask": "u"}
    }

    pm = ProjectModel.from_dict(project)
    eng = PreviewEngine(pm, AudioSim())
    eng.target_mask = "u"
    f = eng.render_frame(0.0)

    assert f[0] != (0, 0, 0)
    assert f[6] != (0, 0, 0)
    assert f[3] == (0, 0, 0)
