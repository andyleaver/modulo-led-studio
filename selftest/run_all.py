"""Run all selftests.

Usage:
  python -m selftest.run_all
"""

import importlib


TEST_MODULES = [
    'selftest.test_modulotion_model',
    'selftest.test_signal_expr_map',
    'selftest.test_codemap_no_holes',
    'selftest.test_preview_smoke',
]


def main():
    failures = []
    for modname in TEST_MODULES:
        try:
            m = importlib.import_module(modname)
            # If module provides main(), call it; else do nothing.
            if hasattr(m, "main") and callable(getattr(m, "main")):
                m.main()
        except Exception as e:
            failures.append((modname, e))

    if failures:
        print("\nFAILED:")
        for modname, e in failures:
            print(f"- {modname}: {e}")
        raise SystemExit(1)

    print("\nOK: all selftests passed")


if __name__ == "__main__":
    main()
