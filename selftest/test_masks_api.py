
def test_masks_api_create_and_validate():
    from app.masks_api import create_composed_mask, validate_all_masks

    p = {"masks": {"a": {"indices": [0,1,2]}, "b": {"start": 2, "end": 4}}}
    p2 = create_composed_mask(p, "u", "union", "a", "b", validate=True, n=50)

    ok, errs = validate_all_masks(p2, n=50)
    assert ok
    assert errs == {}
