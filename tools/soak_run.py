"""Soak runner (Release R9).

Purpose:
- Exercise preview ticks for an extended duration to catch crashes/leaks.
- Does not require UI interaction; uses CoreBridge + PreviewEngine.

Usage:
  python3 tools/soak_run.py --seconds 600 --fps 60

Notes:
- This is a diagnostic tool; it does not mutate projects.
- It prints periodic status and exits non-zero on exceptions.
"""
from __future__ import annotations
import argparse, time, sys, traceback

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--log_every", type=int, default=5)
    args = ap.parse_args(argv)

    from qt.core_bridge import CoreBridge
    core = CoreBridge()

    # Ensure preview engine exists
    core.ensure_full_preview_engine()

    dt = 1.0 / max(1, int(args.fps))
    t0 = time.time()
    last_log = t0
    frames = 0
    try:
        while True:
            now = time.time()
            if now - t0 >= args.seconds:
                break
            # tick core time + audio + signal bus
            try:
                core.tick(dt)
            except Exception:
                # fallback if tick signature differs
                try:
                    core.tick()
                except Exception:
                    raise

            # render a frame (full preview) best-effort
            try:
                eng = getattr(core, "_full_preview_engine", None)
                if eng is not None and hasattr(eng, "render_frame"):
                    eng.render_frame(now)
            except Exception:
                raise

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
