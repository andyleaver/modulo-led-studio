from __future__ import annotations
from app.project_model import get_surface_spec, get_surface_cell_size
from core.surface_compat import get_surface_mapping_values, get_surface_geometry_values
from runtime.resolver import resolve_address, resolve_layer_field
from app.masks_resolver import resolve_mask_to_indices
import math
from pathlib import Path
from params.purpose_contract import ensure as ensure_purpose, clamp as clamp_purpose

from export.exportable_surface import RULES_LAYER_PARAMS_EXPORTABLE
from export.export_eligibility import get_eligibility, ExportStatus
from export.arduino_exporter_blocks import (
    _emit_postfx_blocks,
    _emit_rules_blocks,
)
from export.arduino_exporter_validation import ExportValidationError
from export.arduino_exporter_support import _norm_audio_source
from export.arduino_exporter_layerstack_support import (
    BEHAVIOR_IDS,
    OPERATOR_KIND_IDS,
    MODS_PER_LAYER,
    OPS_PER_LAYER,
    CURVE_IDS,
    MODE_IDS,
    SOURCE_IDS,
    TARGET_PARAM_IDS,
    build_group_index_maps,
    resolve_ui_target_mask_set,
    apply_ui_target_mask,
)


def build_layerstack_export_context(*, project: dict) -> dict:
    """Build the canonical export context used by the layerstack sketch generator."""
    # Geometry/mapping authority must come from canonical SurfaceSpec.
    # Export wiring authority must come from canonical export.hw.
    expcfg = (project.get("export") or {}) if isinstance(project.get("export"), dict) else {}
    hwcfg = expcfg.get("hw") if isinstance(expcfg.get("hw"), dict) else {}
    DBG_PURPOSE = bool(expcfg.get("debug_purpose_serial", False))
    try:
        DBG_BAUD = int(expcfg.get("debug_serial_baud", 115200) or 115200)
    except Exception:
        DBG_BAUD = 115200
    spec = get_surface_spec(project)
    if spec is None:
        raise RuntimeError("Canonical SurfaceSpec missing — Arduino export blocked.")

    surface_kind, surface_count, surface_width, surface_height = get_surface_geometry_values(spec, default_kind="strip", default_count=60)
    m = get_surface_mapping_values(spec)
    if surface_kind == "cells":
        mw = int(surface_width)
        mh = int(surface_height)
        num_leds = int(surface_count)
    else:
        mw = int(surface_count)
        mh = 1
        num_leds = int(surface_count)
    matrix_serp = bool(m["serpentine"])
    flip_x = bool(m["flip_x"])
    flip_y = bool(m["flip_y"])
    rotate = int(m["rotate"])

    led_pin = int(hwcfg.get("data_pin", 6))
    cell = get_surface_cell_size(project)

    postfx_decls, postfx_apply = _emit_postfx_blocks(project=project, surface_kind=surface_kind, num_leds=num_leds)
    rules_decls, rules_apply = _emit_rules_blocks(project=project)

    layers_all = list(project.get("layers", []) or [])
    resolved_layers = []
    for li, L in enumerate(layers_all):
        if not isinstance(L, dict):
            continue
        if (str(L.get("behavior") or "").strip() == "audio_meter"):
            continue
        en = bool(resolve_layer_field(project=project, layer_index=li, field="enabled", runtime=None).value)
        if not en:
            continue
        ordv = resolve_layer_field(project=project, layer_index=li, field="order", runtime=None, default=li).value
        try:
            ordv = int(ordv)
        except Exception:
            ordv = int(li)
        resolved_layers.append((ordv, li, L))
    resolved_layers.sort(key=lambda t: (t[0], t[1]))
    layers = [L for (_o, _li, L) in resolved_layers]
    groups = list(project.get("groups", []) or [])
    zones = list(project.get("zones", []) or [])

    # Export targeting truth: apply project-wide UI target mask (including composed masks)
    # by synthesizing groups for resolved index sets and intersecting per-layer targets.
    # Canonical project-level read is resolver-only; no raw nested ui fallback here.
    ui_mask_set = resolve_ui_target_mask_set(
        project,
        num_leds,
        resolve_address=resolve_address,
        resolve_mask_to_indices=resolve_mask_to_indices,
    )

    # Build a map of existing group index sets for dedupe
    _group_sets, _group_set_to_id = build_group_index_maps(groups, num_leds)

    # behavior ids and export helpers live in export.arduino_exporter_layerstack_support

    # per-layer arrays (defaults)
    L_BEH=[]; LR=[]; LG=[]; LB=[]; L_OP=[]; L_BLEND=[]; L_TK=[]; L_TR=[]
    L_BR=[]; L_SP=[]; L_WD=[]; L_SO=[]; L_DN=[]; L_DIR=[]
    L_R2=[]; L_G2=[]; L_B2=[]; L_RBG=[]; L_GBG=[]; L_BBG=[]; L_DUTY=[]; L_HUEOFF=[]; L_HUESPAN=[]
    L_PF0=[]
    L_PF1=[]
    L_PF2=[]
    L_PF3=[]
    L_PI0=[]
    L_PI1=[]
    L_PI2=[]
    L_PI3=[]
    L_STFP=[]

    # Phase 3.4: Kernel DSL per-layer compiled C++ expressions.
    # Only used when beh_id == 18 (kernel_dsl).
    K_CPP=[]
    # Phase 3.6: Write-the-loop per-layer C++ bodies (only used when beh_id == 23).
    W_CPP=[]

    # Operators/runtime export lookup tables live in export.arduino_exporter_layerstack_support
    OP_KIND = []   # 0=none,1=gain,2=gamma,3=posterize
    OP_P0 = []     # param0 (gain/gamma/levels)

    M_SRC=[]; M_TGT=[]; M_MODE=[]; M_AMT=[]; M_RATE=[]; M_BIAS=[]; M_SMOOTH=[]; M_CURVE=[]; M_PHASE=[]

    for _ord, li, L in resolved_layers:
        beh = str(L.get("behavior","solid")).lower().strip()
        beh_id = BEHAVIOR_IDS.get(beh, 7)
        L_BEH.append(beh_id)

        # Canonical composition fields resolved via universal resolver (one-path)
        op_res = resolve_layer_field(project=project, layer_index=li, field="opacity", runtime=None)
        bm_res = resolve_layer_field(project=project, layer_index=li, field="blend_mode", runtime=None)
        try:
            _layer_opacity = float(op_res.value)
        except Exception:
            _layer_opacity = 1.0
        _layer_opacity = 0.0 if _layer_opacity < 0.0 else (1.0 if _layer_opacity > 1.0 else _layer_opacity)
        _layer_blend_mode = str(bm_res.value or "over").lower().strip()

        params = L.get("params", {}) or {}
        # Phase 2B: sprite/tilemap export variants
        # Encode per-effect variant id into PI0 (raw int16), so firmware can branch deterministically.
        # Tilemap/Sprite:
        #   0=tilemap_sprite, 1=red_hat_runner, 2=mariobros_clockface
        # CA Cluster:
        #   0=brians_brain, 1=game_of_life, 2=elementary_ca, 3=langtons_ant
        # MSGEQ7 Cluster:
        #   0=bars, 1=reactive strobe
        if beh == 'red_hat_runner':
            params = dict(params)
            params.setdefault('pi0', 1)
            params.setdefault('pf1', 0.6)  # jump height
        elif beh == 'mariobros_clockface':
            params = dict(params)
            params.setdefault('pi0', 2)
            params.setdefault('pf1', 0.7)  # digit size / pulse
        elif beh == 'tilemap_sprite':
            params = dict(params)
            params.setdefault('pi0', 0)
        elif beh == 'brians_brain':
            params = dict(params)
            params.setdefault('pi0', 0)
            params.setdefault('pf1', 0.35) # init density
        elif beh == 'game_of_life':
            params = dict(params)
            params.setdefault('pi0', 1)
            params.setdefault('pf1', 0.30) # init density
        elif beh == 'elementary_ca':
            params = dict(params)
            params.setdefault('pi0', 2)
            params.setdefault('pf1', 0.0)  # unused
        elif beh == 'langtons_ant':
            params = dict(params)
            params.setdefault('pi0', 3)
            params.setdefault('pf1', 0.0)  # unused

        elif beh == 'ca_module':
            # CA Module runner: encode module selection into PI0, and module params into PF2/PF3.
            from runtime.ca_modules import list_ca_modules, get_ca_module
            params = dict(params)
            module_name = str(params.get('module_name', 'life_B3S23'))
            mods = list_ca_modules()
            if module_name not in mods:
                raise ExportValidationError(f"[E_CA_MODULE_UNKNOWN] ca_module module_name '{module_name}' not registered")
            midx = mods.index(module_name)
            params.setdefault('pi0', 4 + int(midx))
            # init density
            params.setdefault('pf1', float(params.get('density', 0.25)))
            mod = get_ca_module(module_name)
            if mod is None:
                raise ExportValidationError(f"[E_CA_MODULE_UNKNOWN] ca_module module_name '{module_name}' not registered")
            if mod.kind == 'life2d':
                params.setdefault('pf2', int(params.get('Bmask', (1<<3))))
                params.setdefault('pf3', int(params.get('Smask', (1<<2)|(1<<3))))
            else:
                params.setdefault('pf2', int(params.get('rule', 30)) & 0xFF)
                params.setdefault('pf3', 0)
        elif beh == 'msgeq7_visualizer_575':
            params = dict(params)
            params.setdefault('pi0', 0)
            params.setdefault('pf1', 1.0)  # gain
        elif beh == 'msgeq7_reactive_ino':
            params = dict(params)
            params.setdefault('pi0', 1)
            params.setdefault('pf1', 1.0)  # gain

        elif beh == 'boids_swarm':
            # Boids Swarm (Phase A+E lightweight firmware equivalent: beh_id == 18)
            # Firmware consumes generic channels:
            #   speed   -> sp (0..1)
            #   width   -> wd (0..1)
            #   density -> dn (0..1)
            # Map boids-specific preview params into those generic knobs.
            params = dict(params)
            n = float(params.get('_num_leds', 256) or 256)
            # speed: preview range ~0.2..40
            try:
                bs = float(params.get('boids_speed', 6.0) or 6.0)
            except Exception:
                bs = 6.0
            bs = 0.2 if bs < 0.2 else (40.0 if bs > 40.0 else bs)
            params.setdefault('speed', max(0.0, min(1.0, (bs - 0.2) / (40.0 - 0.2))))
            # width: preview uses boids_strip_width to fold strip into a pseudo-2D grid;
            # use it as a relative blob size.
            try:
                bw = float(params.get('boids_strip_width', 32) or 32)
            except Exception:
                bw = 32.0
            bw = 1.0 if bw < 1.0 else bw
            params.setdefault('width', max(0.0, min(1.0, bw / max(1.0, n))))
            # density: preview boids_count can be large; firmware uses dn to select 1..3 agents.
            try:
                bc = float(params.get('boids_count', 10) or 10)
            except Exception:
                bc = 10.0
            params.setdefault('density', max(0.0, min(1.0, bc / 30.0)))

        elif beh == 'predator_prey':
            # Predator/Prey (Phase A+E lightweight firmware equivalent: beh_id == 19)
            # Firmware consumes generic 'speed' plus purpose channels (pf0 bias).
            params = dict(params)
            try:
                ps = float(params.get('pp_speed', 6.0) or 6.0)
            except Exception:
                ps = 6.0
            ps = 0.2 if ps < 0.2 else (40.0 if ps > 40.0 else ps)
            params.setdefault('speed', max(0.0, min(1.0, (ps - 0.2) / (40.0 - 0.2))))
            params.setdefault('pf0', float(params.get('pf0', 0.5) or 0.5))
            params.setdefault('pi0', int(params.get('seed', 0) or 0) & 0xFFFF)

        elif beh == 'memory_heatmap':
            # Memory Heatmap uses legacy params (mem_inject/mem_decay) in preview.
            # Firmware implementation consumes generic channels:
            #   pf0 = excitation/input (0..1)
            #   pf1 = decay control (0..1)
            #   speed = hotspot wander (0..1-ish)
            #   width = gaussian radius
            # Map legacy params into pf0/pf1 at export time to preserve preview↔export intent.
            params = dict(params)
            try:
                inj = float(params.get('mem_inject', 0.25) or 0.25)
            except Exception:
                inj = 0.25
            # preview allows up to ~2.0; firmware expects 0..1
            params.setdefault('pf0', max(0.0, min(1.0, inj)))

            # Convert legacy per-frame decay factor into a decay-rate (1/s), then into pf1.
            # Legacy: v *= mem_decay each tick (assumed ~60fps).
            try:
                d = float(params.get('mem_decay', 0.985) or 0.985)
            except Exception:
                d = 0.985
            d = 0.80 if d < 0.80 else (0.9999 if d > 0.9999 else d)
            dt_ref = 1.0 / 60.0
            try:
                lam = -math.log(d) / dt_ref  # 1/s
            except Exception:
                lam = 0.5
            # Firmware decay = 0.25 + clamp01(pf1)*1.25
            decay = max(0.25, min(1.50, float(lam)))
            pf1 = (decay - 0.25) / 1.25
            params.setdefault('pf1', max(0.0, min(1.0, pf1)))

            # Provide reasonable defaults if the project didn't set the generic channels.
            params.setdefault('speed', 0.35)
            params.setdefault('width', 0.18)

        # Kernel DSL: compile expression at export time.
        if beh == 'kernel_dsl':
            # Local import to avoid circular imports during app startup.
            from runtime.kernel_dsl import compile_kernel_expr, KernelCompileError
            params = dict(params)
            params.setdefault('pi1', int(params.get('seed', 1337) or 1337))
            expr = str(params.get('kernel_expr', 'fract(sin((x*12.9898+y*78.233+seed)+t)*43758.5453)') or '')
            try:
                kc = compile_kernel_expr(expr)
                K_CPP.append(kc.cpp_expr)
            except KernelCompileError as e:
                raise ExportValidationError(f"[E_KERNEL_DSL_INVALID] kernel_expr invalid: {e}")
        else:
            K_CPP.append("0.0f")

        # Phase 3.6: Kernel C++ body per layer (injected at export time).
        if beh in ("kernel", "fsm_phases"):
            cpp_body = str((params or {}).get("cpp") or "").strip()
            if not cpp_body:
                cpp_body = r"""\
// Default rainbow demo\
float h = fmodf(x + t * 0.1f, 1.0f);\
if (h < 0.0f) h += 1.0f;\
const float s = 1.0f;\
const float v = 1.0f;\
float k = fmodf(h * 6.0f, 6.0f);\
float f = k - floorf(k);\
float p = v * (1.0f - s);\
float q = v * (1.0f - s * f);\
float rr = v * (1.0f - s * (1.0f - f));\
int ki = (int)floorf(k);\
if (ki == 0) { r = v; g = rr; b = p; }\
else if (ki == 1) { r = q; g = v; b = p; }\
else if (ki == 2) { r = p; g = v; b = rr; }\
else if (ki == 3) { r = p; g = q; b = v; }\
else if (ki == 4) { r = rr; g = p; b = v; }\
else { r = v; g = p; b = q; }\
""".strip()
            if "#" in cpp_body:
                raise ExportValidationError("[E_WRITE_LOOP_INVALID] Kernel C++ body may not contain preprocessor directives (#).")
            W_CPP.append(cpp_body)
        else:
            W_CPP.append("")

        params = ensure_purpose(params)
        params = clamp_purpose(params)
        params["_project"] = project
        col = params.get("color", (255,0,0))
        try:
            r,g,b = int(col[0])&255, int(col[1])&255, int(col[2])&255
        except Exception:
            r,g,b = 255,0,0
        LR.append(r); LG.append(g); LB.append(b)

        # secondary color / extra params (defaults are safe even if behavior ignores them)
        # NOTE: color2 is used by some effects; bg is an alias used by stateful demos like bouncer
        bg = params.get("bg", None)
        col2 = bg if bg is not None else params.get("color2", (0,0,255))
        try:
            r2,g2,b2 = int(col2[0])&255, int(col2[1])&255, int(col2[2])&255
        except Exception:
            r2,g2,b2 = 0,0,255
        L_R2.append(r2); L_G2.append(g2); L_B2.append(b2)
        # bg stored separately
        try:
            rb,gb,bb = int(bg[0])&255, int(bg[1])&255, int(bg[2])&255
        except Exception:
            rb,gb,bb = 0,0,0
        L_RBG.append(rb); L_GBG.append(gb); L_BBG.append(bb)
        L_DUTY.append(float(params.get("duty", 0.25)))
        L_HUEOFF.append(int(params.get("hue_offset", 0)) & 255)
        L_HUESPAN.append(float(params.get("hue_span", 1.0)))

        L_BR.append(float(params.get("brightness", 1.0)))
        L_SP.append(float(params.get("speed", 1.0)))
        L_WD.append(float(params.get("width", 0.2)))
        L_SO.append(float(params.get("softness", 0.0)))
        L_DN.append(float(params.get("density", 0.2)))
        L_DIR.append(float(params.get("direction", 1.0)))
        # Optional per-layer float/int params (PF0..PF3 / PI0..PI3). Default to 0 if absent.
        L_PF0.append(float(params.get("pf0", 0.0)))
        L_PF1.append(float(params.get("pf1", 0.0)))
        L_PF2.append(float(params.get("pf2", 0.0)))
        L_PF3.append(float(params.get("pf3", 0.0)))
        L_PI0.append(int(params.get("pi0", 0)))
        L_PI1.append(int(params.get("pi1", 0)))
        L_PI2.append(int(params.get("pi2", 0)))
        L_PI3.append(int(params.get("pi3", 0)))

        op = float(_layer_opacity)
        L_OP.append(op)

        bm = str(_layer_blend_mode or "over").lower().strip()
        bm_id = 0
        if bm=="add": bm_id=1
        elif bm=="max": bm_id=2
        elif bm=="multiply": bm_id=3
        elif bm=="screen": bm_id=4
        L_BLEND.append(bm_id)

        tk = str(L.get("target_kind","all")).lower().strip()
        tk_id = 0
        if tk=="group": tk_id=1
        elif tk=="zone": tk_id=2
        tref = int(L.get("target_ref",0))

        # Apply UI target mask intersection if present
        tk_id, tref = apply_ui_target_mask(
            ui_mask_set=ui_mask_set,
            groups=groups,
            group_sets=_group_sets,
            group_set_to_id=_group_set_to_id,
            zones=zones,
            num_leds=num_leds,
            tk_id=tk_id,
            tref=tref,
        )

        L_TK.append(tk_id)
        L_TR.append(int(tref))

        mods_all = list(L.get("modulotors", []) or [])
        # only enabled modulotors
        mods = []
        for mm in mods_all:
            try:
                if bool(mm.get('enabled', False)):
                    mods.append(mm)
            except Exception:
                pass
        mods = mods[:MODS_PER_LAYER]
        # pad with disabled/none
        while len(mods) < MODS_PER_LAYER:
            mods.append({"source":"none","target":"brightness","mode":"mul","amount":0.0,"rate_hz":0.5,"bias":0.0,"smooth":0.0})

        for m in mods:
            kind = str(m.get("kind","audio")).lower().strip()
            src = _norm_audio_source(str(m.get("source","none")))
            if kind == "lfo":
                src = "lfo_sine"
            M_SRC.append(int(SOURCE_IDS.get(src,0)))
            tgt = str(m.get("target","brightness")).strip()
            M_TGT.append(int(TARGET_PARAM_IDS.get(tgt,0)))
            mm = str(m.get("mode","mul")).strip().lower()
            M_MODE.append(int(MODE_IDS.get(mm,0)))
            M_AMT.append(float(m.get("amount",0.0)))
            M_RATE.append(float(m.get("rate_hz",0.5)))
            M_BIAS.append(float(m.get("bias",0.0)))
            M_SMOOTH.append(float(m.get("smooth",0.0)))
            cv = str(m.get("curve","linear")).lower().strip()
            M_CURVE.append(int(CURVE_IDS.get(cv, 0)))
            M_PHASE.append(float(m.get("phase", 0.0)))

        # Operators: flatten up to OPS_PER_LAYER per layer
        ops_all = list(L.get("operators", []) or [])
        ops = []
        layer_effect_kind = str(L.get("behavior") or "").strip().lower()
        for oi, op in enumerate(ops_all):
            if not isinstance(op, dict):
                continue
            # Slot-0 may be a mirrored behavior entry (legacy LayerStack sync). Treat it as behavior, not PostFX.
            kind0 = str(op.get("kind") or op.get("op") or op.get("type") or "none").strip().lower()
            if oi == 0 and layer_effect_kind and kind0 == layer_effect_kind and kind0 not in OPERATOR_KIND_IDS:
                continue
            if bool(op.get("enabled", True)) is False:
                continue
            ops.append(op)
        ops = ops[:OPS_PER_LAYER]
        while len(ops) < OPS_PER_LAYER:
            ops.append({"kind": "none", "p0": 0.0})

        for op in ops:
            # Operators schema supports both legacy flat form and newer nested params form:
            # - Legacy (fixtures/older saves): {"kind": "gain", "p0": 1.2}
            # - New (UI/preview): {"type": "gain", "params": {"gain": 1.2}, ...}
            params_op = op.get("params") if isinstance(op.get("params"), dict) else {}
            kind = str(op.get("kind") or op.get("op") or op.get("type") or "none").strip().lower()
            kid = OPERATOR_KIND_IDS.get(kind)
            if kid is None:
                raise ExportValidationError(f"Unsupported operator kind for export: {kind!r}")
            kid = int(kid)
            # Normalize parameters
            if kid == 1:
                # gain
                p0 = float(op.get("gain", params_op.get("gain", op.get("p0", 1.0))))
            elif kid == 2:
                # gamma
                p0 = float(op.get("gamma", params_op.get("gamma", op.get("p0", 2.2))))
            elif kid == 3:
                # posterize levels
                p0 = float(op.get("levels", op.get("steps", params_op.get("posterize_levels", op.get("p0", 8)))))
            else:
                p0 = float(op.get("p0", 0.0))
            OP_KIND.append(kid)
            OP_P0.append(p0)

    # Phase 3.4: emit per-layer kernel switch cases (only used for kernel_dsl behavior).
    kernel_cases_lines = []
    for li, expr in enumerate(K_CPP):
        # Keep expression short-ish and safe (already validated by compile_kernel_expr).
        kernel_cases_lines.append(f"    case {li}: v = {expr}; break;")
    kernel_cases = "\n".join(kernel_cases_lines) if kernel_cases_lines else "    default: v = 0.0f; break;"

    # Phase 3.6: emit per-layer write-the-loop kernel switch cases (used for kernel behavior).
    write_loop_cases_lines = []
    for li, body in enumerate(W_CPP):
        bb = str(body or "").strip("\n")
        if not bb.strip():
            continue
        # Validate injected body: keep it simple and safe.
        # - No preprocessor directives / includes
        # - Must at least attempt to assign r/g/b (user contract)
        try:
            import re
            # Disallow common directives/includes. We also block raw '#' to avoid pragma/defines.
            forbidden = ["#", "#include", "#define", "#pragma", "#if", "#elif", "#endif"]
            low = bb.lower()
            if any(tok in low for tok in ["#include", "#define", "#pragma", "#if", "#elif", "#endif"]) or "#" in bb:
                raise ExportValidationError(
                    f"Kernel C++ body for layer {li} contains forbidden preprocessor directives (no #include/#define/#pragma/#if)."
                )
            # Require at least one assignment to r/g/b. (We don't attempt full parsing.)
            if not re.search(r"\b(r|g|b)\s*=", bb):
                raise ExportValidationError(
                    f"Kernel C++ body for layer {li} must assign r/g/b (0..1 floats)."
                )
        except ExportValidationError:
            raise
        except Exception as e:
            from runtime.diagnostics import GLOBAL_DIAGS
            GLOBAL_DIAGS.exception(e, domain="EXPORT", code="KERNEL_CPP_VALIDATE_EXCEPTION", summary="kernel cpp validation exception", details={"layer_index": li})
            raise ExportValidationError(f"Kernel C++ validation failed for layer {li}.")
        # Indent user body inside case scope (6 spaces keeps it aligned in C++).
        ind = "\n".join(["      " + ln for ln in bb.splitlines()])
        write_loop_cases_lines.append(f"    case {li}: {{\n{ind}\n    }} break;")
    write_loop_cases = "\n".join(write_loop_cases_lines)
    # Phase 3.5: CA module export codegen (custom CA rules).
    ca_module_decls_lines = []
    ca_module_case_lines = []
    try:
        from runtime.ca_modules import list_ca_modules, get_ca_module
        ca_mods = list_ca_modules()
    except Exception:
        ca_mods = []
        get_ca_module = None

    def _safe_c_ident(name: str) -> str:
        out = []
        for ch in name:
            if ch.isalnum() or ch == '_':
                out.append(ch)
            else:
                out.append('_')
        s2 = ''.join(out)
        if not s2 or s2[0].isdigit():
            s2 = 'm_' + s2
        return s2

    for midx, mname in enumerate(ca_mods):
        mod = get_ca_module(mname) if get_ca_module else None
        if not mod:
            continue
        fn = _safe_c_ident(mname)
        body = str(mod.cpp_step_body or '').strip("\n")
        ca_module_decls_lines.append(
            f"static inline void ca_module_step_{fn}(const uint8_t* src, uint8_t* dst, int mw, int mh, int num_leds, uint32_t Bmask, uint32_t Smask, uint8_t rule8){{\n{body}\n}}\n"
        )
        ca_module_case_lines.append(
            f"      case {midx}: ca_module_step_{fn}(CA_A, CA_B, mw, mh, NUM_LEDS, (uint32_t)pf2, (uint32_t)pf3, (uint8_t)((int)pf2 & 0xFF)); break;"
        )

    ca_module_decls = "\n".join(ca_module_decls_lines) if ca_module_decls_lines else "// (no CA modules registered)"

    if ca_module_case_lines:
        ca_cases = "\n".join(ca_module_case_lines)
        ca_module_dispatch = (
            "      int mw=0, mh=0;\n"
            "#ifdef MATRIX_WIDTH\n"
            "      mw = (int)MATRIX_WIDTH; mh = (int)MATRIX_HEIGHT;\n"
            "#else\n"
            "      mw = NUM_LEDS; mh = 1;\n"
            "#endif\n"
            "      switch((int)variant - 4){\n"
            f"{ca_cases}\n"
            "      default: break;\n"
            "      }\n"
            "      int n = mw*mh; if(n>NUM_LEDS) n=NUM_LEDS;\n"
            "      for(int ii=0; ii<n; ii++) CA_A[ii]=CA_B[ii];\n"
        )
    else:
        ca_module_dispatch = "      /* no modules */"

    # groups payload
    group_indexes=[]
    group_offs=[]
    group_lens=[]
    off=0
    for g in groups:
        inds = g.get("indices", []) if isinstance(g, dict) else []
        vals=[]
        for v in (inds or []):
            try: vals.append(int(v))
            except Exception: pass
        seen=set(); uniq=[]
        for v in vals:
            if v not in seen:
                seen.add(v); uniq.append(v)
        group_offs.append(off)
        group_lens.append(len(uniq))
        group_indexes.extend(uniq)
        off += len(uniq)

    zone_start=[]
    zone_end=[]
    for z in zones:
        try:
            zone_start.append(int(z.get("start",0)))
            zone_end.append(int(z.get("end",0)))
        except Exception:
            zone_start.append(0); zone_end.append(0)

    # Ensure empty arrays compile
    if not group_offs: group_offs=[0]
    if not group_lens: group_lens=[0]
    if not group_indexes: group_indexes=[0]
    if not zone_start: zone_start=[0]
    if not zone_end: zone_end=[0]


    context = dict(locals())
    context.pop("project", None)
    return context
