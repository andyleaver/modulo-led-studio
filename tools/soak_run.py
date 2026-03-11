"""Soak runner.

Purpose:
- Exercise preview rebuild/render paths for an extended duration to catch crashes/leaks.
- Does not require UI interaction; uses CoreBridge + PreviewEngine.

Usage:
  python3 tools/soak_run.py --seconds 600 --fps 60
"""
from __future__ import annotations
import argparse, time, sys, traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--log_every", type=int, default=5)
    args = ap.parse_args(argv)

    from qt.core_bridge import CoreBridge
    core = CoreBridge()

    # Current CoreBridge API: build a fresh preview engine explicitly.
    if hasattr(core, "rebuild_preview_clean"):
        core.rebuild_preview_clean("soak_start")
    elif hasattr(core, "_rebuild_full_preview_engine"):
        core._rebuild_full_preview_engine()

    dt = 1.0 / max(1, int(args.fps))
    t0 = time.time()
    last_log = t0
    frames = 0
    try:
        while True:
            now = time.time()
            if now - t0 >= args.seconds:
                break

            # Best-effort audio/signal advancement for headless diagnostics runs.
            try:
                if hasattr(core, "_diagnostics_tick_audio"):
                    core._diagnostics_tick_audio()
            except Exception:
                pass

            eng = getattr(core, "_full_preview_engine", None) or getattr(core, "preview_engine", None)
            if eng is None:
                raise RuntimeError("Preview engine unavailable during soak run")

            # Render one frame on the live preview engine.
            if hasattr(eng, "render_frame"):
                eng.render_frame(now)
            else:
                raise RuntimeError("Preview engine has no render_frame()")

            # Keep signal snapshots fresh when available.
            try:
                if hasattr(core, "_update_signals_from_preview"):
                    core._update_signals_from_preview(now)
            except Exception:
                pass

            frames += 1
            if now - last_log >= args.log_every:
                last_log = now
                print(f"[soak] t={now-t0:.1f}s frames={frames}")
            time.sleep(dt)

        print(f"[soak] OK duration={time.time()-t0:.1f}s frames={frames}")
        return 0
    except Exception as e:
        print("[soak] FAIL:", type(e).__name__, e)
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
