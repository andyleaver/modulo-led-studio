def test_project_migrate_adds_uids_and_ui_defaults():
    from app.project_manager import migrate_project_dict
    p = {
        "layout": {"shape": "strip", "num_leds": 10},
        "layers": [{"name": "L1", "behavior": "solid"}],
    }
    p2 = migrate_project_dict(p)
    assert isinstance(p2.get("ui"), dict)
    assert "selected_layer" in p2["ui"]
    assert isinstance(p2.get("layers"), list)
    assert p2["layers"][0].get("uid")
    assert p2["layers"][0].get("__uid")
