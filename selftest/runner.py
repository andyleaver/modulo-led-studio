from __future__ import annotations

"""Minimal selftest runner.

Note: This project has a dedicated exporter selftest suite (tools/export_selftest.py).
This runner intentionally stays lightweight and focuses on repository sanity checks
that should always pass in exporter-only builds.
"""

from pathlib import Path
import compileall
import sys


def _fail(msg: str) -> None:
    raise SystemExit("SELFTEST FAILED: " + msg)


def test_compileall() -> None:
    root = Path(__file__).resolve().parents[1]
    ok = compileall.compile_dir(str(root), quiet=1)
    if not ok:
        _fail("compileall failed")


def test_preflight_if_present() -> None:
    # Optional: if preflight module exists in this branch, run its integrity checks.
    try:
        import preflight  # noqa: F401
        from preflight import (
            check_canonical_manifest_integrity,
            check_capabilities_catalog_parity,
        )
    except Exception:
        return

    check_canonical_manifest_integrity()
    check_capabilities_catalog_parity()



def test_golden_pipeline_order() -> None:
    """Lock the order-of-ops pipeline (behavior -> operators -> postfx -> blend)."""
    try:
        from preview.headless import run_headless
        import json
        from pathlib import Path
    except Exception as e:
        _fail("imports failed for golden_pipeline_order: " + repr(e))
    root = Path(__file__).resolve().parents[1]
    gold_path = root / "fixtures" / "golden_hashes.json"
    proj_path = root / "fixtures" / "projects" / "order_pipeline_lock.json"
    audio_path = root / "fixtures" / "demo_audio_1s.jsonl"
    if not gold_path.exists() or not proj_path.exists() or not audio_path.exists():
        _fail("missing golden fixture assets for pipeline order test")
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    exp = gold.get("order_pipeline_lock")
    if not exp:
        _fail("golden_hashes missing order_pipeline_lock entry")

    exp2 = gold.get("order_pipeline_lock_matrix8x8")
    if not exp2:
        _fail("golden_hashes missing order_pipeline_lock_matrix8x8 entry")

    exp3 = gold.get("order_pipeline_lock_matrix8x8_mapstress_mapped")
    if not exp3:
        _fail("golden_hashes missing order_pipeline_lock_matrix8x8_mapstress_mapped entry")

    exp4 = gold.get("order_pipeline_lock_matrix8x8_mapstress2_mapped")
    if not exp4:
        _fail("golden_hashes missing order_pipeline_lock_matrix8x8_mapstress2_mapped entry")
    got = run_headless(proj_path, audio_path, frames=30, fps=30.0)
    if got != exp:
        _fail(f"pipeline order golden hash mismatch: expected {exp} got {got}")

    proj2_path = root / "fixtures" / "projects" / "order_pipeline_lock_matrix8x8.json"
    if not proj2_path.exists():
        _fail("missing matrix pipeline order fixture")
    got2 = run_headless(proj2_path, audio_path, frames=30, fps=30.0)
    if got2 != exp2:
        _fail(f"matrix pipeline order golden hash mismatch: expected {exp2} got {got2}")

    # Mapping stress: hash the *mapped* buffer so mapping regressions are detected.
    try:
        from preview.audio_input import AudioInput
        from models.io import load_project
        from preview.preview_engine import PreviewEngine
        from preview.mapping import MatrixMapping, xy_index, logical_dims
        import hashlib
    except Exception as e:
        _fail("imports failed for mapping stress: " + repr(e))

    proj3_path = root / "fixtures" / "projects" / "order_pipeline_lock_matrix8x8_mapstress.json"
    if not proj3_path.exists():
        _fail("missing mapping stress pipeline fixture")

    project3 = load_project(proj3_path)
    audio3 = AudioInput()
    audio3.recorder.load(audio_path)
    audio3.recorder.start_play(0.0)
    audio3.mode = "playback"
    audio3.gain = 1.0
    audio3.smoothing = 0.0
    eng3 = PreviewEngine(project=project3, audio=audio3, fixed_dt=1.0/60.0)

    layout3 = getattr(project3, "layout", None) or {}
    mw = int(getattr(layout3, "mw", 0) or 0)
    mh = int(getattr(layout3, "mh", 0) or 0)
    # Prefer canonical layout fields (serpentine/flip_x/flip_y/rotate), fallback to nested mapping dict if present.
    mapping3 = getattr(layout3, "mapping", None) or {}
    serp = getattr(layout3, "serpentine", None)
    fx = getattr(layout3, "flip_x", None)
    fy = getattr(layout3, "flip_y", None)
    rot = getattr(layout3, "rotate", None)
    if serp is None:
        serp = bool(getattr(mapping3, "serpentine", False) or getattr(mapping3, "mode", "") == "serpentine")
    if fx is None:
        fx = bool(getattr(mapping3, "flip_x", False))
    if fy is None:
        fy = bool(getattr(mapping3, "flip_y", False))
    if rot is None:
        rot = int(getattr(mapping3, "rotate", 0) or 0)
    mm = MatrixMapping(w=mw, h=mh, serpentine=bool(serp), flip_x=bool(fx), flip_y=bool(fy), rotate=int(rot or 0))
    w2, h2 = logical_dims(mm)

    def buf_to_bytes(buf) -> bytes:
        out = bytearray()
        if not buf:
            return bytes(out)
        v0 = buf[0]
        if isinstance(v0, int):
            for x in buf:
                out.extend(int(x).to_bytes(4, "little", signed=False))
        else:
            for r, g, b in buf:
                out.append(int(r) & 0xFF)
                out.append(int(g) & 0xFF)
                out.append(int(b) & 0xFF)
        return bytes(out)

    def mapped_bytes(buf) -> bytes:
        # Produce a deterministic bytes stream in logical row-major order.
        out = bytearray()
        for y in range(h2):
            for x in range(w2):
                idx = xy_index(mm, x, y)
                if idx < 0 or idx >= len(buf):
                    out.extend(b"\x00\x00\x00\x00")
                    continue
                v = buf[idx]
                if isinstance(v, int):
                    out.extend(int(v).to_bytes(4, "little", signed=False))
                else:
                    r, g, b = v
                    out.append(int(r) & 0xFF)
                    out.append(int(g) & 0xFF)
                    out.append(int(b) & 0xFF)
        return bytes(out)

    h = hashlib.sha256()
    t = 0.0
    dt = 1.0 / 30.0
    for _ in range(30):
        audio3.step(t)
        buf = eng3.render_frame(t)
        h.update(mapped_bytes(buf))
        t += dt
    got3 = h.hexdigest()
    if got3 != exp3:
        _fail(f"matrix mapping stress golden hash mismatch: expected {exp3} got {got3}")

    # Mapping stress variant 2 (rotate/flip variant): also hash mapped buffer.
    proj4_path = root / "fixtures" / "projects" / "order_pipeline_lock_matrix8x8_mapstress2.json"
    if not proj4_path.exists():
        _fail("missing mapping stress2 pipeline fixture")

    project4 = load_project(proj4_path)
    audio4 = AudioInput()
    audio4.recorder.load(audio_path)
    audio4.recorder.start_play(0.0)
    audio4.mode = "playback"
    audio4.gain = 1.0
    audio4.smoothing = 0.0
    eng4 = PreviewEngine(project=project4, audio=audio4, fixed_dt=1.0/60.0)

    layout4 = getattr(project4, "layout", None) or {}
    mw4 = int(getattr(layout4, "mw", 0) or 0)
    mh4 = int(getattr(layout4, "mh", 0) or 0)
    mapping4 = getattr(layout4, "mapping", None) or {}
    serp4 = getattr(layout4, "serpentine", None)
    fx4 = getattr(layout4, "flip_x", None)
    fy4 = getattr(layout4, "flip_y", None)
    rot4 = getattr(layout4, "rotate", None)
    if serp4 is None:
        serp4 = bool(getattr(mapping4, "serpentine", False) or getattr(mapping4, "mode", "") == "serpentine")
    if fx4 is None:
        fx4 = bool(getattr(mapping4, "flip_x", False))
    if fy4 is None:
        fy4 = bool(getattr(mapping4, "flip_y", False))
    if rot4 is None:
        rot4 = int(getattr(mapping4, "rotate", 0) or 0)
    mm4 = MatrixMapping(w=mw4, h=mh4, serpentine=bool(serp4), flip_x=bool(fx4), flip_y=bool(fy4), rotate=int(rot4 or 0))
    w4, h4 = logical_dims(mm4)

    def mapped_bytes4(buf) -> bytes:
        out = bytearray()
        for y in range(h4):
            for x in range(w4):
                idx = xy_index(mm4, x, y)
                if idx < 0 or idx >= len(buf):
                    out.extend(b"\x00\x00\x00\x00")
                    continue
                v = buf[idx]
                if isinstance(v, int):
                    out.extend(int(v).to_bytes(4, "little", signed=False))
                else:
                    r, g, b = v
                    out.append(int(r) & 0xFF)
                    out.append(int(g) & 0xFF)
                    out.append(int(b) & 0xFF)
        return bytes(out)

    h4s = hashlib.sha256()
    t4 = 0.0
    dt4 = 1.0 / 30.0
    for _ in range(30):
        audio4.step(t4)
        buf4 = eng4.render_frame(t4)
        h4s.update(mapped_bytes4(buf4))
        t4 += dt4
    got4 = h4s.hexdigest()
    if got4 != exp4:
        _fail(f"matrix mapping stress2 golden hash mismatch: expected {exp4} got {got4}")


def main() -> None:
    test_compileall()
    test_preflight_if_present()
    test_golden_pipeline_order()
    print("✅ selftest.runner passed.")


if __name__ == "__main__":
    main()