from __future__ import annotations

import json
from pathlib import Path

from export.arduino_exporter_block_common import TOKEN_RE, EXPORT_MARKER

def _emit_rules_blocks(*, project: dict) -> tuple[str, str]:
    """Phase 6.3: Arduino Rules runtime (minimal deterministic subset).

    Supports:
      - triggers: tick, threshold, rising
      - actions: set_var, add_var, flip_toggle
      - expressions: const, signal (scale+bias, optional as_bool)
    Supports (exportable subset):
      - set_layer_param for 'opacity', 'brightness', 'operator.gain', 'operator.gamma' (deterministic subset)
    Notes:
      - Variables must be declared in project['variables'] (fail-closed on unknown var).
      - Uses export.signal_expr_map for known exportable signals (audio_*).
    """
    p = project or {}
    rules = p.get("rules") or []
    if not isinstance(rules, list) or not rules:
        return ("// Rules disabled\n", "// Rules disabled\n")

    # Import mapping lazily
    try:
        from export.signal_expr_map import arduino_expr_for_signal
    except Exception:
        arduino_expr_for_signal = None

    # Variables (explicit names)
    vars0 = (p.get("variables") or {}) if isinstance(p.get("variables"), dict) else {}
    num_vars = vars0.get("number") if isinstance(vars0.get("number"), dict) else {}
    tog_vars = vars0.get("toggle") if isinstance(vars0.get("toggle"), dict) else {}

    # Stable order by (name,id)
    def _rk(r: dict):
        rr = r if isinstance(r, dict) else {}
        return (str(rr.get("name","") or ""), str(rr.get("id","") or ""))
    rules_list = [r for r in rules if isinstance(r, dict)]
    rules_list.sort(key=_rk)

    # Sanitize identifiers
    def _sid(s: str) -> str:
        s = re.sub(r"[^A-Za-z0-9_]+", "_", str(s or ""))
        if not s:
            s = "x"
        if s[0].isdigit():
            s = "_" + s
        return s

    # Build var index maps
    num_names = list(num_vars.keys())
    tog_names = list(tog_vars.keys())
    num_map = {str(k): i for i, k in enumerate(num_names)}
    tog_map = {str(k): i for i, k in enumerate(tog_names)}

    decls: list[str] = []
    decls.append("// RULES: minimal deterministic runtime")
    decls.append(f"#define MODULA_RULES_ENABLED 1")
    decls.append(f"static const uint8_t VNUM_N = {len(num_names)};")
    decls.append(f"static const uint8_t VTOG_N = {len(tog_names)};")
    if num_names:
        decls.append("static float VNUM[VNUM_N] = {" + ", ".join(f"{float(num_vars.get(n,0.0)):.6f}f" for n in num_names) + "};")
    else:
        decls.append("static float VNUM[1] = {0.0f};")
    if tog_names:
        decls.append("static bool VTOG[VTOG_N] = {" + ", ".join("true" if bool(tog_vars.get(n, False)) else "false" for n in tog_names) + "};")
    else:
        decls.append("static bool VTOG[1] = {false};")

    # Rule state arrays
    n_rules = len([r for r in rules_list if str(r.get("id","") or "")])
    decls.append(f"static const uint8_t RULES_N = {n_rules};")
    decls.append("static bool RULE_PREV[RULES_N];")
    decls.append("static bool RULE_LATCH[RULES_N]; // threshold state w/ hysteresis")
    decls.append("")

    # Helpers
    decls.append("static inline float rules_read_signal(uint8_t sk){")
    decls.append("  // 0.. = built-in signals encoded per rule; unknown => 0")
    decls.append("  switch(sk){")
    # We'll generate per-rule signal read snippets later (by unique signal), but simplest:
    decls.append("    default: return 0.0f;")
    decls.append("  }")
    decls.append("}")
    decls.append("")
    # We'll not use rules_read_signal; we will inline expressions in rules loop.

    apply: list[str] = []
    apply.append("// --- Rules evaluate (runs once per frame) ---")
    apply.append("  // NOTE: rules are evaluated before layer params/behaviors")
    apply.append("  for (uint8_t ri=0; ri<RULES_N; ri++){ /* init safety */ if (now==0) { RULE_PREV[ri]=false; RULE_LATCH[ri]=false; } }")
    apply.append("  // Rules in stable order (generated)")
    apply.append("  {")
    apply.append("    uint8_t __ri = 0;")

    # Emit each rule as a block
    for r in rules_list:
        rid = str(r.get("id","") or "")
        if not rid:
            continue
        enabled = bool(r.get("enabled", True))
        if not enabled:
            continue

        trigger = str(r.get("trigger","tick") or "tick")
        when = r.get("when") if isinstance(r.get("when"), dict) else {}
        w_sig = str((when or {}).get("signal","") or "")
        w_op = str((when or {}).get("op",">") or ">")
        w_val = float((when or {}).get("value", 0.0) or 0.0)
        w_hyst = float((when or {}).get("hyst", 0.0) or 0.0)

        # Conditions
        conds = r.get("conditions") if isinstance(r.get("conditions"), list) else []
        cond_mode = str(r.get("cond_mode","all") or "all").lower()
        if cond_mode not in ("all","any"):
            cond_mode = "all"

        action = r.get("action") if isinstance(r.get("action"), dict) else {}
        kind = str(action.get("kind","") or "")
        # Phase A3.6+: allow only the canonical exportable surface for set_layer_param.
        if kind == "set_layer_param":
            _p = str(action.get("param","") or "").strip().lower()
            if _p not in set(RULES_LAYER_PARAMS_EXPORTABLE):
                allowed = ", ".join([repr(x) for x in RULES_LAYER_PARAMS_EXPORTABLE])
                raise ExportValidationError(
                    f"[E_RULE_LAYER_PARAM_UNSUPPORTED] rules rule '{rid}' uses set_layer_param for '{_p}' (exportable params: {allowed})."
                )

            if _p == "operator.gain":
                # Resolve deterministic operator slot for gain on the referenced layer.
                try:
                    li = int(action.get("layer", 0) or 0)
                except Exception:
                    li = 0
                layers0 = p.get("layers") or []
                layer = layers0[li] if (isinstance(layers0, list) and 0 <= li < len(layers0)) else None
                ops0 = (layer or {}).get("operators") if isinstance(layer, dict) else None
                if not isinstance(ops0, list):
                    ops0 = []
                slot = -1
                for i, od in enumerate(ops0[:2]):  # OPS_PER_LAYER is 2
                    if not isinstance(od, dict):
                        continue
                    if not bool(od.get("enabled", True)):
                        continue
                    if str(od.get("kind","") or "").strip().lower() == "gain":
                        slot = i
                        break
                if slot < 0:
                    raise ExportValidationError(
                        f"[E_RULE_OP_GAIN_NO_OPERATOR] rules rule '{rid}' requests operator.gain on layer {li}, but that layer has no enabled gain operator in the first {2} slots."
                    )

                # Store for the emitter
                action["_op_gain_slot"] = slot

            if _p == "operator.gamma":
                # Resolve deterministic operator slot for gamma on the referenced layer.
                try:
                    li = int(action.get("layer", 0) or 0)
                except Exception:
                    li = 0
                layers0 = p.get("layers") or []
                layer = layers0[li] if (isinstance(layers0, list) and 0 <= li < len(layers0)) else None
                ops0 = (layer or {}).get("operators") if isinstance(layer, dict) else None
                if not isinstance(ops0, list):
                    ops0 = []
                slot = -1
                for i, od in enumerate(ops0[:2]):
                    if not isinstance(od, dict):
                        continue
                    if not bool(od.get("enabled", True)):
                        continue
                    if str(od.get("kind","") or "").strip().lower() == "gamma":
                        slot = i
                        break
                if slot < 0:
                    raise ExportValidationError(
                        f"[E_RULE_OP_GAMMA_NO_OPERATOR] rules rule '{rid}' requests operator.gamma on layer {li}, but that layer has no enabled gamma operator in the first {2} slots."
                    )
                action["_op_gamma_slot"] = slot

        var_kind = str(action.get("var_kind","number") or "number")
        var_name = str(action.get("var","") or "")

        # Validate var existence
        if kind in ("set_var","add_var"):
            if var_kind != "number":
                raise ExportValidationError(f"[E_RULE_BAD_VAR_KIND] rules rule '{rid}' kind={kind} requires var_kind=number.")
            if var_name not in num_map:
                raise ExportValidationError(f"[E_RULE_UNKNOWN_VAR] rules rule '{rid}' refers to unknown number var '{var_name}'. Define it in project.variables.number.")
        if kind == "flip_toggle":
            if var_kind != "toggle":
                raise ExportValidationError(f"[E_RULE_BAD_VAR_KIND] rules rule '{rid}' flip_toggle requires var_kind=toggle.")
            if var_name not in tog_map:
                raise ExportValidationError(f"[E_RULE_UNKNOWN_VAR] rules rule '{rid}' refers to unknown toggle var '{var_name}'. Define it in project.variables.toggle.")

        # Expression for action
        expr = action.get("expr") if isinstance(action.get("expr"), dict) else {"src":"const","const":0.0}
        src = str(expr.get("src","const") or "const")
        scale = float(expr.get("scale", 1.0) or 1.0)
        bias = float(expr.get("bias", 0.0) or 0.0)
        as_bool = bool(expr.get("as_bool", False))

        def _ardu_expr_signal(sigkey: str) -> str:
            """Map a project signal key -> Arduino expression.

            This exporter supports both legacy and new-style keys:
              - Legacy audio keys: audio_energy, audio_mono_0..6, audio_left_0..6, audio_right_0..6
              - New signal-bus keys: audio.energy, audio.mono0..6, audio.L0..6, audio.R0..6
              - Variable keys: vars.number.<name>, vars.toggle.<name>

            Unknown keys resolve to 0.0f (fail-closed semantics for expressions).
            """

            if not isinstance(sigkey, str) or not sigkey.strip():
                return "0.0f"
            k = sigkey.strip()

            # Variables (Phase 6.2 bridge)
            if k.startswith("vars.number."):
                nm = k[len("vars.number."):]
                if nm in num_map:
                    return f"(float)(VNUM[{num_map[nm]}])"
                return "0.0f"
            if k.startswith("vars.toggle."):
                nm = k[len("vars.toggle."):]
                if nm in tog_map:
                    return f"(VTOG[{tog_map[nm]}] ? 1.0f : 0.0f)"
                return "0.0f"

            # Normalize new-style audio keys to legacy keys understood by signal_expr_map
            # audio.energy -> audio_energy
            if k == "audio.energy":
                k = "audio_energy"
            elif k.startswith("audio.mono"):
                suf = k[len("audio.mono"):]
                if suf.isdigit():
                    k = f"audio_mono_{suf}"
            elif k.startswith("audio.L"):
                suf = k[len("audio.L"):]
                if suf.isdigit():
                    k = f"audio_left_{suf}"
            elif k.startswith("audio.R"):
                suf = k[len("audio.R"):]
                if suf.isdigit():
                    k = f"audio_right_{suf}"

            if arduino_expr_for_signal is None:
                return "0.0f"
            ex = arduino_expr_for_signal(k)
            return "0.0f" if ex is None else f"(float)({ex})"

        def _emit_expr(e: dict) -> str:
            ssrc = str(e.get("src","const") or "const")
            sscale = float(e.get("scale", 1.0) or 1.0)
            sbias = float(e.get("bias", 0.0) or 0.0)
            sas_bool = bool(e.get("as_bool", False))
            if ssrc == "signal":
                sk = str(e.get("signal","") or "")
                base = _ardu_expr_signal(sk)
                out = f"(({base})*{sscale:.6f}f + {sbias:.6f}f)"
            else:
                c = float(e.get("const", 0.0) or 0.0)
                out = f"(({c:.6f}f)*{sscale:.6f}f + {sbias:.6f}f)"
            if sas_bool:
                return f"(({out}) > 0.5f ? 1.0f : 0.0f)"
            return out

        # Build trigger predicate expression
        # We'll compute a float cur from when.signal (or 0)
        cur_expr = _ardu_expr_signal(w_sig) if w_sig else "0.0f"

        op = w_op if w_op in (">",">=","<","<=","==") else ">"
        thr = f"{w_val:.6f}f"
        hyst = abs(w_hyst)
        apply.append(f"    // Rule {rid}")
        apply.append(f"    {{")
        apply.append(f"      float cur = {cur_expr};")
        # conds evaluation
        if conds:
            if cond_mode == "all":
                apply.append("      bool cond_ok = true;")
            else:
                apply.append("      bool cond_ok = false;")
            for c in conds:
                if not isinstance(c, dict):
                    continue
                csig = str(c.get("signal","") or "")
                cop = str(c.get("op",">") or ">")
                cval = float(c.get("value",0.0) or 0.0)
                cop = cop if cop in (">",">=","<","<=","==") else ">"
                cexpr = _ardu_expr_signal(csig) if csig else "0.0f"
                apply.append(f"      float cv = {cexpr};")
                apply.append(f"      bool cpass = (cv {cop} {cval:.6f}f);")
                if cond_mode == "all":
                    apply.append("      cond_ok = cond_ok && cpass;")
                else:
                    apply.append("      cond_ok = cond_ok || cpass;")
        else:
            apply.append("      bool cond_ok = true;")

        # Trigger logic
        if trigger == "tick":
            apply.append("      bool fired = cond_ok;")
        elif trigger == "rising":
            apply.append("      bool now_on = (cur > 0.5f);")
            apply.append("      bool fired = cond_ok && (now_on && !RULE_PREV[__ri]);")
            apply.append("      RULE_PREV[__ri] = now_on;")
        else:  # threshold
            apply.append(f"      float thr = {thr};")
            apply.append(f"      float hyst = {hyst:.6f}f;")
            apply.append("      bool prev = RULE_LATCH[__ri];")
            # hysteresis: if prev true, off threshold thr-hyst, else on threshold thr+hyst (for >/>=). For < cases we invert sense
            if op in ("<","<="):
                apply.append("      float on_thr = thr - hyst;")
                apply.append("      float off_thr = thr + hyst;")
                apply.append("      bool now_on = prev ? (cur <= off_thr) : (cur <= on_thr);")
            else:
                apply.append("      float on_thr = thr + hyst;")
                apply.append("      float off_thr = thr - hyst;")
                apply.append("      bool now_on = prev ? (cur >= off_thr) : (cur >= on_thr);")
            apply.append("      RULE_LATCH[__ri] = now_on;")
            # fired on entering true
            apply.append("      bool fired = cond_ok && (now_on && !prev);")

        # Action
        if kind in ("set_var","add_var","flip_toggle"):
            if kind == "flip_toggle":
                vi = tog_map[var_name]
                apply.append(f"      if (fired) {{ VTOG[{vi}] = !VTOG[{vi}]; }}")
            else:
                vi = num_map[var_name]
                ex = _emit_expr(expr)
                if kind == "set_var":
                    apply.append(f"      if (fired) {{ VNUM[{vi}] = {ex}; }}")
                else:
                    apply.append(f"      if (fired) {{ VNUM[{vi}] += {ex}; }}")
        elif kind == "set_layer_param":
            # Exportable subset: per-layer runtime overrides
            # Supported params: opacity, brightness
            try:
                li = int(action.get("layer", 0) or 0)
            except Exception:
                li = 0
            _p = str(action.get("param", "opacity") or "opacity").strip().lower()
            conflict = str(action.get("conflict", "last") or "last").strip().lower()
            if conflict not in ("last", "first", "max", "min"):
                conflict = "last"
            ex = _emit_expr(expr)

            apply.append("      if (fired) {")
            apply.append(f"        const int li = {li};")
            apply.append("        if (li >= 0 && li < LAYERS) {")

            if _p == "brightness":
                apply.append(f"          float v = clamp01((float)({_arduino_clamp_expr('layer_brightness', ex)}));")
                if conflict == "first":
                    apply.append("          if (!L_BR_SET[li]) { L_BR_RT[li] = v; L_BR_SET[li] = true; }")
                elif conflict == "max":
                    apply.append("          if (!L_BR_SET[li]) { L_BR_RT[li] = v; L_BR_SET[li] = true; } else { L_BR_RT[li] = fmaxf(L_BR_RT[li], v); }")
                elif conflict == "min":
                    apply.append("          if (!L_BR_SET[li]) { L_BR_RT[li] = v; L_BR_SET[li] = true; } else { L_BR_RT[li] = fminf(L_BR_RT[li], v); }")
                else:
                    apply.append("          L_BR_RT[li] = v; L_BR_SET[li] = true; ")
            elif _p == "operator.gain":
                # Rules→Operators bridge: set gain operator param0 at a deterministic slot.
                # Uses first gain operator slot on the layer (computed at export time).
                # If no gain operator exists for this layer, export is blocked earlier.
                try:
                    oi = int(action.get("op_index", -1) or -1)
                except Exception:
                    oi = -1
                # If not specified, we'll use a precomputed slot stored on action by the exporter.
                try:
                    oi2 = int(action.get("_op_gain_slot", -1) or -1)
                except Exception:
                    oi2 = -1
                if oi < 0:
                    oi = oi2
                if oi < 0:
                    oi = 0
                apply.append(f"          const int oi = {oi};")
                apply.append("          if (oi >= 0 && oi < OPS_PER_LAYER) {")
                apply.append(f"            float v = (float)({_arduino_clamp_expr('operator.gain', ex)});")
                apply.append("            int idx = li * OPS_PER_LAYER + oi;")
                if conflict == "first":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; }")
                elif conflict == "max":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; } else { OP_P0_RT[idx] = fmaxf(OP_P0_RT[idx], v); }")
                elif conflict == "min":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; } else { OP_P0_RT[idx] = fminf(OP_P0_RT[idx], v); }")
                else:
                    apply.append("            OP_P0_RT[idx] = v; OP_P0_SET[idx] = true;")
                apply.append("          }")
            elif _p == "operator.gamma":
                # Rules→Operators bridge: set gamma operator param0 at a deterministic slot.
                # Uses first gamma operator slot on the layer (computed at export time).
                # If no gamma operator exists for this layer, export is blocked earlier.
                try:
                    oi = int(action.get("op_index", -1) or -1)
                except Exception:
                    oi = -1
                # If not specified, we'll use a precomputed slot stored on action by the exporter.
                try:
                    oi2 = int(action.get("_op_gamma_slot", -1) or -1)
                except Exception:
                    oi2 = -1
                if oi < 0:
                    oi = oi2
                if oi < 0:
                    oi = 0
                apply.append(f"          const int oi = {oi};")
                apply.append("          if (oi >= 0 && oi < OPS_PER_LAYER) {")
                apply.append(f"            float v = (float)({_arduino_clamp_expr('gamma', ex)});")
                apply.append("            int idx = li * OPS_PER_LAYER + oi;")
                if conflict == "first":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; }")
                elif conflict == "max":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; } else { OP_P0_RT[idx] = fmaxf(OP_P0_RT[idx], v); }")
                elif conflict == "min":
                    apply.append("            if (!OP_P0_SET[idx]) { OP_P0_RT[idx] = v; OP_P0_SET[idx] = true; } else { OP_P0_RT[idx] = fminf(OP_P0_RT[idx], v); }")
                else:
                    apply.append("            OP_P0_RT[idx] = v; OP_P0_SET[idx] = true;")
                apply.append("          }")
            elif _p == "project.postfx.trail_amount":
                # Rules→PostFX bridge: set global trail amount (0..1) as uint8 0..255.
                apply.append(f"          float vf = clamp01((float)({_arduino_clamp_expr('project.postfx.trail_amount', ex)}));")
                apply.append("          uint8_t v = (uint8_t)(vf * 255.0f + 0.5f);")
                if conflict == "first":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; }")
                elif conflict == "max":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; } else { PFX_TRAIL_RT = (PFX_TRAIL_RT > v) ? PFX_TRAIL_RT : v; }")
                elif conflict == "min":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; } else { PFX_TRAIL_RT = (PFX_TRAIL_RT < v) ? PFX_TRAIL_RT : v; }")
                else:
                    apply.append("          PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; ")
            elif _p == "project.postfx.bleed_amount":
                # Rules→PostFX bridge: set global bleed amount (0..1) as uint8 0..255.
                apply.append(f"          float vf = clamp01((float)({_arduino_clamp_expr('project.postfx.bleed_amount', ex)}));")
                apply.append("          uint8_t v = (uint8_t)(vf * 255.0f + 0.5f);")
                if conflict == "first":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; }")
                elif conflict == "max":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; } else { PFX_BLEED_RT = (PFX_BLEED_RT > v) ? PFX_BLEED_RT : v; }")
                elif conflict == "min":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; } else { PFX_BLEED_RT = (PFX_BLEED_RT < v) ? PFX_BLEED_RT : v; }")
                else:
                    apply.append("          PFX_BLEED_RT = v; PFX_BLEED_SET = true; ")
            elif _p == "project.postfx.bleed_radius":
                # Rules→PostFX bridge: set global bleed radius (1..2).
                apply.append(f"          float vf = (float)({_arduino_clamp_expr('project.postfx.bleed_radius', ex)});")
                apply.append("          int rv = (int)(vf + 0.5f);")
                apply.append("          if (rv < 1) rv = 1; if (rv > 2) rv = 2;")
                apply.append("          uint8_t v = (uint8_t)rv;")
                if conflict == "first":
                    apply.append("          if (!PFX_BLEED_R_SET) { PFX_BLEED_R_RT = v; PFX_BLEED_R_SET = true; }")
                elif conflict == "max":
                    apply.append("          if (!PFX_BLEED_R_SET) { PFX_BLEED_R_RT = v; PFX_BLEED_R_SET = true; } else { PFX_BLEED_R_RT = (PFX_BLEED_R_RT > v) ? PFX_BLEED_R_RT : v; }")
                elif conflict == "min":
                    apply.append("          if (!PFX_BLEED_R_SET) { PFX_BLEED_R_RT = v; PFX_BLEED_R_SET = true; } else { PFX_BLEED_R_RT = (PFX_BLEED_R_RT < v) ? PFX_BLEED_R_RT : v; }")
                else:
                    apply.append("          PFX_BLEED_R_RT = v; PFX_BLEED_R_SET = true; ")
            else:
                # opacity
                apply.append(f"          float v = clamp01((float)({_arduino_clamp_expr('opacity', ex)}));")
                if conflict == "first":
                    apply.append("          if (!L_OP_SET[li]) { L_OP_RT[li] = v; L_OP_SET[li] = true; }")
                elif conflict == "max":
                    apply.append("          if (!L_OP_SET[li]) { L_OP_RT[li] = v; L_OP_SET[li] = true; } else { L_OP_RT[li] = fmaxf(L_OP_RT[li], v); }")
                elif conflict == "min":
                    apply.append("          if (!L_OP_SET[li]) { L_OP_RT[li] = v; L_OP_SET[li] = true; } else { L_OP_RT[li] = fminf(L_OP_RT[li], v); }")
                else:
                    apply.append("          L_OP_RT[li] = v; L_OP_SET[li] = true; ")

            apply.append("        }")
            apply.append("      }")
        else:
            apply.append("      // Unsupported action kind (ignored)")
        apply.append("    }")
        apply.append("    __ri++;")
    apply.append("  }")
    apply.append("  // --- end rules ---")

    return ("\n".join(decls) + "\n", "\n".join(apply) + "\n")

def _arduino_clamp_expr(param_key: str, expr: str) -> str:
    """Return an Arduino expression that clamps expr to PARAMS min/max for that key."""
    try:
        from params.registry import PARAMS
    except Exception:
        return expr
    meta = PARAMS.get(param_key, {})
    t = meta.get("type", "float")
    mn = meta.get("min", None)
    mx = meta.get("max", None)
    if mn is None and mx is None:
        return expr
    if mn is None: mn = 0.0
    if mx is None: mx = 1.0
    if t == "int":
        return f"clampi((int)round({expr}), (int){int(mn)}, (int){int(mx)})"
    return f"clampf({expr}, (float){float(mn)}, (float){float(mx)})"

def _norm_audio_source(s: str) -> str:
    s = (s or "none").strip().lower()
    # Accept UI signal-bus style names like "audio.energy" and "audio.mono0"
    if s.startswith("audio."):
        s = s[6:]
    # Legacy UI labels
    if s in ("energy", "none", "lfo_sine"):
        return s
    # Normalize band names: mono0-6, l0-6, r0-6 (with optional whitespace)
    import re
    m = re.match(r"^(mono|l|r)\s*([0-6])$", s)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = re.match(r"^(mono|l|r)([0-6])$", s)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return s

__all__ = ["TOKEN_RE", "EXPORT_MARKER", "_emit_rules_blocks", "_arduino_clamp_expr", "_norm_audio_source"]
