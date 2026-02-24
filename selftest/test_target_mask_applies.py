def test_target_mask_filters_blend_output():
    # Minimal integration test: render two frames with and without target_mask and ensure output differs
    from preview.preview_engine import PreviewEngine
    from preview.audio import AudioSim
    from models.project_model import ProjectModel

    # project: one solid red layer (exportable behavior) over black base
    project = {
        "layout": {"shape": "strip", "num_leds": 10, "count": 10},
        "layers": [
            {"name": "L1", "behavior": "solid", "params": {"color": [255, 0, 0]}, "opacity": 1.0, "blend_mode": "normal",
             "target_kind": "all", "target_ref": 0},
        ],
        "masks": {
            "m": {"indices": [0,1,2]}
        },
        "ui": {}
    }

    pm = ProjectModel.from_dict(project)
    eng = PreviewEngine(pm, AudioSim())
    # without target mask
    eng.target_mask = None
    f0 = eng.render_frame(0.0)

    # with target mask: only first 3 pixels red
    eng.target_mask = "m"
    f1 = eng.render_frame(0.1)

    # Expect pixel 0 differs? Actually both frames for pixel0 may be red, but pixel5 should differ.
    assert f0[5] != f1[5], "target_mask should affect pixels outside mask"
    assert f1[0] == f0[0], "pixel inside mask should remain red"
