"""Selftests for modulotion_model.apply_modulotion

Run:
  python -m selftest.test_modulotion_model
"""

from app.modulotion_model import ModulotionBinding, apply_modulotion


def _assert_close(a: float, b: float, eps: float = 1e-9):
    if abs(a - b) > eps:
        raise AssertionError(f"{a} != {b} (eps={eps})")


def test_add():
    b = ModulotionBinding(target_param="x", signal_key="time_ms", op="add", amount=2.0, bias=1.0)
    out = apply_modulotion(10.0, 3.0, b)  # v=3*2+1=7; 10+7=17
    _assert_close(out, 17.0)


def test_mul():
    b = ModulotionBinding(target_param="x", signal_key="time_ms", op="mul", amount=0.5, bias=0.0)
    out = apply_modulotion(10.0, 4.0, b)  # v=2; 10*2=20
    _assert_close(out, 20.0)


def test_clamp01():
    b = ModulotionBinding(target_param="x", signal_key="time_ms", op="clamp01", amount=1.0, bias=0.0)
    _assert_close(apply_modulotion(10.0, -2.0, b), 0.0)
    _assert_close(apply_modulotion(10.0, 0.2, b), 0.2)
    _assert_close(apply_modulotion(10.0, 2.0, b), 1.0)


def test_lerp():
    b = ModulotionBinding(target_param="x", signal_key="time_ms", op="lerp", amount=1.0, bias=0.0, out_min=10.0, out_max=20.0)
    _assert_close(apply_modulotion(999.0, 0.0, b), 10.0)
    _assert_close(apply_modulotion(999.0, 0.5, b), 15.0)
    _assert_close(apply_modulotion(999.0, 1.0, b), 20.0)
    _assert_close(apply_modulotion(999.0, 2.0, b), 20.0)  # clamped t


def test_output_clamp():
    b = ModulotionBinding(target_param="x", signal_key="time_ms", op="add", amount=10.0, bias=0.0, out_min=0.0, out_max=5.0)
    _assert_close(apply_modulotion(0.0, 1.0, b), 5.0)


def main():
    test_add()
    test_mul()
    test_clamp01()
    test_lerp()
    test_output_clamp()
    print("OK: modulotion_model selftests passed")


if __name__ == "__main__":
    main()
