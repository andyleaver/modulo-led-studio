
def test_composed_masks_resolve():
    from app.masks_resolver import resolve_mask_to_indices

    project = {
        "masks": {
            "a": {"indices": [0, 1, 2, 10]},
            "b": {"start": 2, "end": 4},
            "u": {"op": "union", "a": "a", "b": "b"},
            "i": {"op": "intersect", "a": "a", "b": "b"},
            "s": {"op": "subtract", "a": "a", "b": "b"},
            "x": {"op": "xor", "a": "a", "b": "b"},
        }
    }

    assert sorted(resolve_mask_to_indices(project, "u", n=20)) == [0, 1, 2, 3, 4, 10]
    assert sorted(resolve_mask_to_indices(project, "i", n=20)) == [2]
    assert sorted(resolve_mask_to_indices(project, "s", n=20)) == [0, 1, 10]
    assert sorted(resolve_mask_to_indices(project, "x", n=20)) == [0, 1, 3, 4, 10]
