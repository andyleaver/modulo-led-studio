"""Run all selftests.

Usage:
  python -m selftest.run_all
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import traceback

import selftest

def _iter_test_modules() -> list[str]:
    mods: list[str] = []
    for info in pkgutil.iter_modules(selftest.__path__):
        name = str(info.name)
        if not name.startswith("test_"):
            continue
        mods.append(f"selftest.{name}")
    return sorted(mods)

def _run_module(modname: str) -> tuple[bool, list[str]]:
    notes: list[str] = []
    try:
        m = importlib.import_module(modname)
    except Exception:
        return False, [traceback.format_exc()]

    try:
        if hasattr(m, "run") and callable(getattr(m, "run")):
            rv = m.run()
            if isinstance(rv, tuple) and len(rv) == 2:
                ok, msg = bool(rv[0]), str(rv[1])
                notes.append(msg)
                return ok, notes
            notes.append("run()")
            return True, notes

        if hasattr(m, "main") and callable(getattr(m, "main")):
            m.main()
            notes.append("main()")
            return True, notes

        ran_any = False
        for name, fn in inspect.getmembers(m, inspect.isfunction):
            if name.startswith("test_") and fn.__module__ == m.__name__:
                fn()
                notes.append(name)
                ran_any = True
        if ran_any:
            return True, notes

        notes.append("no run/main/test_* entrypoint")
        return True, notes
    except Exception:
        return False, notes + [traceback.format_exc()]

def main() -> None:
    failures: list[tuple[str, list[str]]] = []
    modules = _iter_test_modules()
    print("=== Modulo Full Selftest Runner ===")
    print(f"Discovered {len(modules)} test modules")
    for modname in modules:
        ok, notes = _run_module(modname)
        if ok:
            if notes:
                print(f"[PASS] {modname} :: {'; '.join(notes)}")
            else:
                print(f"[PASS] {modname}")
        else:
            failures.append((modname, notes))
            first = notes[-1] if notes else "unknown failure"
            print(f"[FAIL] {modname} :: {first.splitlines()[-1]}")

    if failures:
        print("\nFAILED:")
        for modname, notes in failures:
            print(f"\n--- {modname} ---")
            for n in notes:
                print(n)
        raise SystemExit(1)

    print("\nOK: all discovered selftests passed")

if __name__ == "__main__":
    main()
