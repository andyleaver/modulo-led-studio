"""Preview smoke test: load a known demo fixture and render frames.

Catches small regressions that previously caused blank preview / crashes.
"""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    import json

    from models.io import load_project
    from preview.preview_engine import PreviewEngine
    from preview.audio_input import AudioInput

    root = Path(__file__).resolve().parents[1]
    demo = root / "demos" / "demo_red_hat_runner_rules_v6.json"
    if not demo.exists():
        raise AssertionError(f"missing demo fixture: {demo}")

    # Load project
    project = load_project(demo)

    # Use simulated audio (stable)
    audio = AudioInput()
    audio.mode = "sim"

    eng = PreviewEngine(project=project, audio=audio, fixed_dt=1.0 / 60.0)

    # Render a few frames and ensure we get nonzero pixels
    nonzero_counts = []
    t = 0.0
    for i in range(5):
        buf = eng.render_frame(t)
        # buf is expected to be a list/array of packed ints
        nz = 0
        try:
            for v in buf:
                if int(v) != 0:
                    nz += 1
        except Exception as e:
            raise AssertionError(f"render_frame returned unexpected buffer type: {type(buf).__name__}: {e}")
        nonzero_counts.append(nz)
        t += 1.0 / 30.0

    if max(nonzero_counts) <= 0:
        raise AssertionError(f"preview smoke: all frames blank (nonzero_counts={nonzero_counts})")

    # Layer toggle probe (if there is at least one layer)
    pd = getattr(eng, 'project_data', None)
    if isinstance(pd, dict) and isinstance(pd.get('layers', None), list) and pd['layers']:
        # toggle first layer enabled -> should change output (often to blank)
        pd2 = json.loads(json.dumps(pd))  # deep copy
        pd2['layers'][0]['enabled'] = False
        eng.project_data = pd2
        buf_off = eng.render_frame(t)
        nz_off = sum(1 for v in buf_off if int(v) != 0)
        # Not strictly required to be 0, but should differ from enabled render.
        if nz_off == nonzero_counts[-1]:
            raise AssertionError(f"layer toggle did not change render output (nz_on={nonzero_counts[-1]} nz_off={nz_off})")


if __name__ == "__main__":
    main()
