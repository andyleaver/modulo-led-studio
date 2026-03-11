"""Composition parity probe.

Goal: prove that composition is engine-correct (no half-baked wiring):

- layers[i].enabled
- layers[i].opacity
- layers[i].order (list order)
- layers[i].blend_mode (over/add/max/multiply/screen)

This probe is deterministic and returns a cases list of subtests.

Outputs PASS/FAIL dict with evidence suitable for Diagnostics tab.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional

RGB = Tuple[int, int, int]

def _hash_rgb(buf: List[RGB]) -> str:
    """Stable tiny hash for evidence."""
    import hashlib

    m = hashlib.sha256()
    for r, g, b in buf:
        m.update(bytes((r & 255, g & 255, b & 255)))
    return m.hexdigest()[:16]

def _render_first_pixel(project: Dict[str, Any]) -> Tuple[RGB, str, Optional[str]]:
    """Render once and return (px0, hash, fail_reason)."""
    from preview.preview_project_bridge import make_preview_engine_from_project_dict

    pe, _issues, _clean = make_preview_engine_from_project_dict(project, fixed_dt=1.0 / 60.0)
    out = pe.render_project(pe.project, t=0.0, dt=0.0, audio=None)
    leds = out.get("leds") if isinstance(out, dict) else out
    if not isinstance(leds, list) or not leds:
        return (0, 0, 0), "", f"unexpected buffer type={type(leds).__name__}"

    px0 = leds[0]
    try:
        px = (int(px0[0]) & 255, int(px0[1]) & 255, int(px0[2]) & 255)
    except Exception:
        px = (0, 0, 0)
    return px, _hash_rgb([(int(r) & 255, int(g) & 255, int(b) & 255) for (r, g, b) in leds]), None

def _mk_project(*, layers: List[Dict[str, Any]], count: int = 10) -> Dict[str, Any]:
    from app.project_model import build_surface_dict

    count = max(1, int(count))
    return {
        "surface": build_surface_dict(kind="strip", count=count),
        "layers": layers,
        "postfx": {},
        "rules": [],
        "meta": {},
    }

def _ok_rgb(px: RGB, exp: Tuple[float, float, float], *, tol: int = 1) -> bool:
    return (
        abs(px[0] - exp[0]) <= tol
        and abs(px[1] - exp[1]) <= tol
        and abs(px[2] - exp[2]) <= tol
    )

def run_probe(*, app_id: str = "", diagnostics=None) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {"app_id": app_id}

    try:
        # Import check (explicit)
        from preview.preview_project_bridge import make_preview_engine_from_project_dict  # noqa: F401
    except Exception as e:
        return {
            "probe_id": "P5.COMPOSITION_PARITY_CASES",
            "pass": False,
            "summary": "Failed to import canonical preview bridge",
            "fail_reason": f"{type(e).__name__}: {e}",
            "evidence": evidence,
        }

    subtests: List[Dict[str, Any]] = []

    def add_case(name: str, project: Dict[str, Any], exp: Tuple[float, float, float], *, tol: int = 1):
        try:
            px0, h, fail = _render_first_pixel(project)
        except Exception as e:
            px0, h, fail = (0, 0, 0), "", f"{type(e).__name__}: {e}"
        ok = (fail is None) and _ok_rgb(px0, exp, tol=tol)
        subtests.append(
            {
                "name": name,
                "pass": bool(ok),
                "px0": px0,
                "exp": (float(exp[0]), float(exp[1]), float(exp[2])),
                "tol": int(tol),
                "hash": h,
                "fail_reason": fail if fail else (None if ok else f"expected~{exp} got {px0}"),
            }
        )

    # Case 1: over/alpha blend with opacity (green over red at 0.5)
    layers = [
        {
            "id": "L1",
            "name": "BaseRed",
            "enabled": True,
            "opacity": 1.0,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [255, 0, 0]},
        },
        {
            "id": "L2",
            "name": "TopGreenHalf",
            "enabled": True,
            "opacity": 0.5,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [0, 255, 0]},
        },
    ]
    add_case("over_opacity_0.5", _mk_project(layers=layers), (127.5, 127.5, 0.0), tol=1)

    # Case 2: enabled toggle (layer2 disabled => pure red)
    layers2 = [dict(layers[0]), dict(layers[1])]
    layers2[1]["enabled"] = False
    add_case("layer2_disabled", _mk_project(layers=layers2), (255.0, 0.0, 0.0), tol=0)

    # Case 3: order matters with two half-opacity layers
    layers_a = [
        {
            "id": "A",
            "name": "RedHalf",
            "enabled": True,
            "opacity": 0.5,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [255, 0, 0]},
        },
        {
            "id": "B",
            "name": "GreenHalf",
            "enabled": True,
            "opacity": 0.5,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [0, 255, 0]},
        },
    ]
    add_case("order_red_then_green", _mk_project(layers=layers_a), (63.75, 127.5, 0.0), tol=1)
    layers_b = [layers_a[1], layers_a[0]]
    add_case("order_green_then_red", _mk_project(layers=layers_b), (127.5, 63.75, 0.0), tol=1)

    # Case 4: add blend (base + layer*opacity)
    layers_add = [
        {
            "id": "A",
            "name": "Red100",
            "enabled": True,
            "opacity": 1.0,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [100, 0, 0]},
        },
        {
            "id": "B",
            "name": "GreenAdd200half",
            "enabled": True,
            "opacity": 0.5,
            "blend_mode": "add",
            "behavior": "solid",
            "params": {"color": [0, 200, 0]},
        },
    ]
    add_case("blend_add", _mk_project(layers=layers_add), (100.0, 100.0, 0.0), tol=0)

    # Case 5: multiply blend
    layers_mul = [
        {
            "id": "A",
            "name": "Base200",
            "enabled": True,
            "opacity": 1.0,
            "blend_mode": "over",
            "behavior": "solid",
            "params": {"color": [200, 200, 0]},
        },
        {
            "id": "B",
            "name": "Mul128_255_half",
            "enabled": True,
            "opacity": 0.5,
            "blend_mode": "multiply",
            "behavior": "solid",
            "params": {"color": [128, 255, 0]},
        },
    ]
    exp_r = (200.0 * (128.0 / 255.0)) * 0.5 + 200.0 * 0.5
    exp_g = (200.0 * (255.0 / 255.0)) * 0.5 + 200.0 * 0.5
    add_case("blend_multiply", _mk_project(layers=layers_mul), (exp_r, exp_g, 0.0), tol=1)

    passed = [t for t in subtests if t.get("pass")]
    failed = [t for t in subtests if not t.get("pass")]

    evidence["subtests"] = subtests
    evidence["pass_count"] = len(passed)
    evidence["fail_count"] = len(failed)

    ok_all = len(failed) == 0
    return {
        "probe_id": "P5.COMPOSITION_PARITY_CASES",
        "pass": bool(ok_all),
        "summary": f"Composition cases PASS ({len(passed)}/{len(subtests)})" if ok_all else f"Composition cases FAIL ({len(passed)}/{len(subtests)})",
        "fail_reason": None if ok_all else (failed[0].get("fail_reason") if failed else "unknown"),
        "evidence": evidence,
    }
