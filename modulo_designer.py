import os
import sys
from datetime import datetime, timezone

def _write_crash_log(exc: BaseException) -> None:
    """Best-effort crash log writer."""
    try:
        import traceback
        here = os.path.dirname(os.path.abspath(__file__))
        logs = os.path.join(here, "user_data", "logs")
        os.makedirs(logs, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(logs, f"crash_{ts}.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Modulo crash log\n")
            f.write(f"UTC: {ts}\n\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        try:
            print(f"[Modulo] Crash log written to: {path}")
        except Exception:
            pass
    except Exception:
        pass

def main() -> None:
    argv = list(sys.argv[1:])
    if "--bypass-era" in argv:
        os.environ["MODULO_BYPASS_ERA"] = "1"
        argv = [a for a in argv if a != "--bypass-era"]
        sys.argv = [sys.argv[0], *argv]
    # Qt-only app entrypoint
    # Ensure core extension registries are initialized before UI loads.
    # (Mods may register additional hooks during startup.)
    import runtime.ca_modules  # noqa: F401
    import runtime.long_memory_health  # noqa: F401
    import app.mods_loader  # noqa: F401
    import export.targets.targets_health  # noqa: F401
    from qt.core_bridge import CoreBridge
    from qt.qt_app import run_qt

    here = os.path.dirname(os.path.abspath(__file__))

    core = CoreBridge()
    run_qt(core)

if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        _write_crash_log(e)
        raise
