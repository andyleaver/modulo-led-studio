
def test_zones_ops_registry_imports_and_ops():
    from app.zones_ops_registry import list_zone_ops, get_zone_op

    ops = list_zone_ops()
    keys = [o.key for o in ops]
    assert "union" in keys and "intersect" in keys and "subtract" in keys and "xor" in keys

    a = {"indices": [0, 1, 2, 10]}
    b = {"start": 2, "end": 4}

    u = get_zone_op("union").apply(a, b, n=20)
    assert u == [0, 1, 2, 3, 4, 10]

    i = get_zone_op("intersect").apply(a, b, n=20)
    assert i == [2]

    s = get_zone_op("subtract").apply(a, b, n=20)
    assert s == [0, 1, 10]

    x = get_zone_op("xor").apply(a, b, n=20)
    assert x == [0, 1, 3, 4, 10]
