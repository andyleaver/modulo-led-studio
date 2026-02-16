# Qt-only entry for `python -m app`
from qt.core_bridge import CoreBridge
from qt.qt_app import run_qt

def main() -> None:
    core = CoreBridge()
    run_qt(core)

if __name__ == "__main__":
    main()
