from __future__ import annotations
"""Hot reload behaviors/effects modules safely.

Goal: allow scaffolding an effect from UI, then reloading registry without full app restart.
This is best-effort; in Python, hot reload is never perfect, but for newly-created modules
(and simple edits) it is reliable enough.

Strategy:
- Remove existing effect modules from sys.modules
- Re-import behaviors.effects package modules
- Rebuild REGISTRY by re-registering behavior defs

Registry behavior:
- registry.register() populates REGISTRY
- reload should clear REGISTRY and re-import effects

We keep this strictly in dev workflow; runtime correctness still enforced by preflight.
"""

import importlib
import pkgutil
import sys
from types import ModuleType

def reload_effects() -> tuple[bool, str]:
    try:
        import behaviors.registry as reg
        import behaviors.effects as effects_pkg

        # Clear registry
        reg.REGISTRY.clear()

        # Remove old effect modules from sys.modules so new files are discoverable.
        prefix = "behaviors.effects."
        to_del = [m for m in list(sys.modules.keys()) if m.startswith(prefix)]
        for m in to_del:
            del sys.modules[m]

        # Reload the package itself (ensures pkgutil sees new files)
        importlib.invalidate_caches()
        importlib.reload(effects_pkg)

        # Re-import all modules in behaviors.effects
        count = 0
        for modinfo in pkgutil.iter_modules(effects_pkg.__path__, effects_pkg.__name__ + "."):
            importlib.import_module(modinfo.name)
            count += 1

        if not reg.REGISTRY:
            return False, "Reload ran but REGISTRY is empty (unexpected)."
        return True, f"Reloaded effects: {count} modules, {len(reg.REGISTRY)} registered effects."
    except Exception as e:
        return False, f"Reload failed: {e}"
