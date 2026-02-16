def test_mask_cycle_detection():
    from app.masks_resolver import resolve_mask_to_indices
    project = {
        "masks": {
            "a": {"op": "union", "a": "b", "b": {"indices":[1]}},
            "b": {"op": "union", "a": "a", "b": {"indices":[2]}},
        }
    }
    try:
        resolve_mask_to_indices(project, "a", n=100)
        assert False, "Expected cycle detection error"
    except RuntimeError as e:
        assert "cycle" in str(e).lower()
