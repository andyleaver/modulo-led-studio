"""Deterministic preview render harness (v1).

Example:
  python3 scripts/mod_test_harness.py --effect mod_example_wave --frames 60 --leds 60
"""

from __future__ import annotations

import argparse
import hashlib

from behaviors.registry import get_effect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--effect', required=True)
    ap.add_argument('--frames', type=int, default=60)
    ap.add_argument('--leds', type=int, default=60)
    ap.add_argument('--dt', type=float, default=1.0/30.0)
    args = ap.parse_args()

    eff = get_effect(args.effect)
    if eff is None:
        raise SystemExit(f"Unknown effect: {args.effect}")

    fn = eff.preview_emit
    h = hashlib.sha256()
    t = 0.0
    for _ in range(max(1, args.frames)):
        frame = fn(num_leds=args.leds, params={}, t=t, dt=args.dt, state=None, layout=None, audio=None)
        for (r, g, b) in frame:
            h.update(bytes([int(r) & 255, int(g) & 255, int(b) & 255]))
        t += args.dt

    print(h.hexdigest())


if __name__ == '__main__':
    main()
