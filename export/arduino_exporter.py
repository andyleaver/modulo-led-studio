from __future__ import annotations
import re
from export.preconditions import check as _check_preconditions
from pathlib import Path
from typing import Tuple
from params.purpose_contract import ensure as ensure_purpose, clamp as clamp_purpose

# Exportable surface matrix (single source of truth)
from export.exportable_surface import RULES_LAYER_PARAMS_EXPORTABLE
from export.export_eligibility import get_eligibility, ExportStatus

TOKEN_RE = re.compile(r"@@[A-Z0-9_]+@@")

# Stamp used to prove which exporter produced a given .ino.
# This gets embedded into the generated sketch header and also validated post-render.
EXPORT_MARKER = "MODULO_EXPORT"


def _emit_postfx_blocks(*, project: dict, shape: str, num_leds: int) -> tuple[str, str]:
    """Phase 7F: Arduino PostFX blocks (decls + apply code), memory-safe limits.

    Supports:
      - strip: bleed radius=1 (3-tap blur mix) + trail blend
      - cells/matrix: bleed radius=1 (self + 4-neighbors) using XY(x,y) mapping + trail blend

    Auto-disables for large LED counts on memory-limited boards.
    """
    pf = (project or {}).get("postfx") or {}
    bleed_amount = float(pf.get("bleed_amount", 0.0) or 0.0)
    bleed_radius = int(pf.get("bleed_radius", 1) or 1)
    trail_amount = float(pf.get("trail_amount", 0.0) or 0.0)

    shape_s = str(shape).lower().strip()
    if shape_s not in ("strip", "cells"):
        return ("// PostFX disabled (unsupported layout)\\n", "// PostFX disabled\\n")

    # Enable PostFX emission if base config uses it OR Rules V6 can override it at runtime.
    uses_trail_override = False
    uses_bleed_override = False
    try:
        for r in (project or {}).get("rules_v6") or []:
            if not isinstance(r, dict) or not bool(r.get("enabled", True)):
                continue
            act = r.get("action") if isinstance(r.get("action"), dict) else {}
            if str(act.get("kind", "") or "") != "set_layer_param":
                continue
            _pp = str(act.get("param", "") or "").strip().lower()
            if _pp == "postfx_trail":
                uses_trail_override = True
            elif _pp in ("postfx_bleed", "postfx_bleed_radius"):
                uses_bleed_override = True
            if uses_trail_override and uses_bleed_override:
                break
    except Exception:
        uses_trail_override = False
        uses_bleed_override = False

    enabled = (bleed_amount > 0.0) or (trail_amount > 0.0) or uses_trail_override or uses_bleed_override
    if not enabled:
        return ("// PostFX disabled\\n", "// PostFX disabled\\n")

    # Export-safe clamp: generated code supports radius 1..2.
    if bleed_radius > 2:
        bleed_radius = 2
    if bleed_radius < 1:
        bleed_radius = 1
    bleed_amount = 0.0 if bleed_amount < 0.0 else (1.0 if bleed_amount > 1.0 else bleed_amount)
    trail_amount = 0.0 if trail_amount < 0.0 else (1.0 if trail_amount > 1.0 else trail_amount)

    b_u = int(round(bleed_amount * 255.0))
    t_u = int(round(trail_amount * 255.0))
    inv_t = 255 - t_u

    decls: list[str] = []
    decls.append("// POSTFX (Phase 7F): strip + cells (limited)")
    decls.append("// PostFX may auto-disable for large LED counts (memory safety).")
    decls.append("#if defined(__AVR_ATmega328P__)")
    decls.append("  #if (NUM_LEDS <= 120)")
    decls.append("    #define MODULA_POSTFX_ENABLED 1")
    decls.append("  #else")
    decls.append("    #define MODULA_POSTFX_ENABLED 0")
    decls.append("  #endif")
    decls.append("#else")
    decls.append("  #if (NUM_LEDS <= 300)")
    decls.append("    #define MODULA_POSTFX_ENABLED 1")
    decls.append("  #else")
    decls.append("    #define MODULA_POSTFX_ENABLED 0")
    decls.append("  #endif")
    decls.append("#endif")
    decls.append("")
    decls.append("#if MODULA_POSTFX_ENABLED")
    decls.append("  CRGB _postfx_prev[NUM_LEDS];")
    decls.append("  // Runtime overrides (Rules V6)")
    decls.append(f"  const uint8_t PFX_TRAIL_BASE = {t_u};")
    decls.append(f"  uint8_t PFX_TRAIL_RT = {t_u};")
    decls.append("  bool PFX_TRAIL_SET = false;")
    decls.append(f"  const uint8_t PFX_BLEED_BASE = {b_u};")
    decls.append(f"  uint8_t PFX_BLEED_RT = {b_u};")
    decls.append("  bool PFX_BLEED_SET = false;")
    decls.append(f"  const uint8_t PFX_BLEED_R_BASE = {int(bleed_radius)};")
    decls.append(f"  uint8_t PFX_BLEED_R_RT = {int(bleed_radius)};")
    decls.append("  bool PFX_BLEED_R_SET = false;")
    decls.append("#endif")
    decls.append("")

    apply: list[str] = []
    apply.append("#if MODULA_POSTFX_ENABLED")
    apply.append("  // Capture previous output for trail")
    apply.append("  for (int i=0;i<NUM_LEDS;i++){ _postfx_prev[i] = leds[i]; }")
    apply.append("")

    if (b_u > 0) or uses_bleed_override:
        if shape_s == "strip":
            apply.append("  // Spatial bleed (strip, radius=1..2): mix with avg(neighbors)")
            apply.append("  const uint8_t bleed = PFX_BLEED_RT;")
            apply.append("  uint8_t radius_u = PFX_BLEED_R_RT;")
            apply.append("  uint8_t radius = (radius_u < 1) ? 1 : ((radius_u > 2) ? 2 : radius_u);")
            apply.append("  if (bleed > 0) {")
            apply.append("  int r = (int)radius;")
            apply.append("  for (int i=0;i<NUM_LEDS;i++){")
            apply.append("    CRGB self  = leds[i];")
            apply.append("    uint16_t sr = 0, sg = 0, sb = 0; uint8_t cnt = 0;")
            apply.append("    int j0 = i - r; if (j0 < 0) j0 = 0;")
            apply.append("    int j1 = i + r; if (j1 >= NUM_LEDS) j1 = NUM_LEDS - 1;")
            apply.append("    for (int j=j0;j<=j1;j++){ CRGB c = leds[j]; sr += c.r; sg += c.g; sb += c.b; cnt++; }")
            apply.append("    uint16_t ar = sr / cnt;")
            apply.append("    uint16_t ag = sg / cnt;")
            apply.append("    uint16_t ab = sb / cnt;")
            apply.append("    leds[i].r = uint8_t((uint16_t(self.r) * (255 - bleed) + ar * bleed) / 255);")
            apply.append("    leds[i].g = uint8_t((uint16_t(self.g) * (255 - bleed) + ag * bleed) / 255);")
            apply.append("    leds[i].b = uint8_t((uint16_t(self.b) * (255 - bleed) + ab * bleed) / 255);")
            apply.append("  }")
            apply.append("  }")  # close bleed if
            apply.append("")
        else:
            apply.append("  // Spatial bleed (cells, radius=1..2): avg(neighborhood) using XY() mapping")
            apply.append("  // Requires MATRIX_W/MATRIX_H and XY(x,y) helper emitted by exporter.")
            apply.append("  const uint8_t bleed = PFX_BLEED_RT;")
            apply.append("  uint8_t radius_u = PFX_BLEED_R_RT;")
            apply.append("  uint8_t radius = (radius_u < 1) ? 1 : ((radius_u > 2) ? 2 : radius_u);")
            apply.append("  if (bleed > 0) {")
            apply.append("  int r = (int)radius;")
            apply.append("  for (int y=0;y<MATRIX_H;y++){")
            apply.append("    for (int x=0;x<MATRIX_W;x++){")
            apply.append("      int i = XY(x,y);")
            apply.append("      CRGB self = leds[i];")
            apply.append("      uint16_t sr = 0, sg = 0, sb = 0; uint8_t cnt = 0;")
            apply.append("      for (int dy=-r;dy<=r;dy++){")
            apply.append("        int yy = y + dy; if (yy < 0 || yy >= MATRIX_H) continue;")
            apply.append("        for (int dx=-r;dx<=r;dx++){")
            apply.append("          int xx = x + dx; if (xx < 0 || xx >= MATRIX_W) continue;")
            apply.append("          CRGB c = leds[XY(xx,yy)]; sr += c.r; sg += c.g; sb += c.b; cnt++; ")
            apply.append("        }")
            apply.append("      }")
            apply.append("      uint16_t ar = sr / cnt;")
            apply.append("      uint16_t ag = sg / cnt;")
            apply.append("      uint16_t ab = sb / cnt;")
            apply.append("      leds[i].r = uint8_t((uint16_t(self.r) * (255 - bleed) + ar * bleed) / 255);")
            apply.append("      leds[i].g = uint8_t((uint16_t(self.g) * (255 - bleed) + ag * bleed) / 255);")
            apply.append("      leds[i].b = uint8_t((uint16_t(self.b) * (255 - bleed) + ab * bleed) / 255);")
            apply.append("    }")
            apply.append("  }")
            apply.append("  }")  # close bleed if
            apply.append("")

    # Trail blend: out = prev*trail + current*(1-trail)
    # Uses PFX_TRAIL_RT so Rules V6 can override trail at runtime.
    apply.append("  // Trail blend: out = prev*trail + current*(1-trail)")
    apply.append("  const uint8_t trail = PFX_TRAIL_RT;")
    apply.append("  const uint8_t invTrail = (uint8_t)(255 - trail);")
    apply.append("  for (int i=0;i<NUM_LEDS;i++){")
    apply.append("    leds[i].r = uint8_t((uint16_t(_postfx_prev[i].r)*trail + uint16_t(leds[i].r)*invTrail)/255);")
    apply.append("    leds[i].g = uint8_t((uint16_t(_postfx_prev[i].g)*trail + uint16_t(leds[i].g)*invTrail)/255);")
    apply.append("    leds[i].b = uint8_t((uint16_t(_postfx_prev[i].b)*trail + uint16_t(leds[i].b)*invTrail)/255);")
    apply.append("  }")

    apply.append("#else")
    apply.append("  // PostFX disabled (LED count too large / board memory safety).")
    apply.append("#endif")
    apply.append("")

    return ("\n".join(decls) + "\n", "\n".join(apply) + "\n")
def _emit_rules_v6_blocks(*, project: dict) -> tuple[str, str]:
    """Phase 6.3: Arduino Rules V6 runtime (minimal deterministic subset).

    Supports:
      - triggers: tick, threshold, rising
      - actions: set_var, add_var, flip_toggle
      - expressions: const, signal (scale+bias, optional as_bool)
    Supports (exportable subset):
      - set_layer_param for 'opacity', 'brightness', 'op_gain', 'op_gamma' (deterministic subset)
    Notes:
      - Variables must be declared in project['variables'] (fail-closed on unknown var).
      - Uses export.signal_expr_map for known exportable signals (audio_*).
    """
    p = project or {}
    rules = p.get("rules_v6") or []
    if not isinstance(rules, list) or not rules:
        return ("// Rules V6 disabled\n", "// Rules V6 disabled\n")

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
    decls.append("// RULES_V6 (Phase 6.3): minimal deterministic runtime")
    decls.append(f"#define MODULA_RULES_V6_ENABLED 1")
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
    apply.append("// --- Rules V6 evaluate (runs once per frame) ---")
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
                    f"[E_RULE_LAYER_PARAM_UNSUPPORTED] rules_v6 rule '{rid}' uses set_layer_param for '{_p}' (exportable params: {allowed})."
                )

            if _p == "op_gain":
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
                        f"[E_RULE_OP_GAIN_NO_OPERATOR] rules_v6 rule '{rid}' requests op_gain on layer {li}, but that layer has no enabled gain operator in the first {2} slots."
                    )

                # Store for the emitter
                action["_op_gain_slot"] = slot

            if _p == "op_gamma":
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
                        f"[E_RULE_OP_GAMMA_NO_OPERATOR] rules_v6 rule '{rid}' requests op_gamma on layer {li}, but that layer has no enabled gamma operator in the first {2} slots."
                    )
                action["_op_gamma_slot"] = slot

        var_kind = str(action.get("var_kind","number") or "number")
        var_name = str(action.get("var","") or "")

        # Validate var existence
        if kind in ("set_var","add_var"):
            if var_kind != "number":
                raise ExportValidationError(f"[E_RULE_BAD_VAR_KIND] rules_v6 rule '{rid}' kind={kind} requires var_kind=number.")
            if var_name not in num_map:
                raise ExportValidationError(f"[E_RULE_UNKNOWN_VAR] rules_v6 rule '{rid}' refers to unknown number var '{var_name}'. Define it in project.variables.number.")
        if kind == "flip_toggle":
            if var_kind != "toggle":
                raise ExportValidationError(f"[E_RULE_BAD_VAR_KIND] rules_v6 rule '{rid}' flip_toggle requires var_kind=toggle.")
            if var_name not in tog_map:
                raise ExportValidationError(f"[E_RULE_UNKNOWN_VAR] rules_v6 rule '{rid}' refers to unknown toggle var '{var_name}'. Define it in project.variables.toggle.")

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
            elif _p == "op_gain":
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
                apply.append(f"            float v = (float)({_arduino_clamp_expr('operator_gain', ex)});")
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
            elif _p == "op_gamma":
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
            elif _p == "postfx_trail":
                # Rules→PostFX bridge: set global trail amount (0..1) as uint8 0..255.
                apply.append(f"          float vf = clamp01((float)({_arduino_clamp_expr('postfx_trail', ex)}));")
                apply.append("          uint8_t v = (uint8_t)(vf * 255.0f + 0.5f);")
                if conflict == "first":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; }")
                elif conflict == "max":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; } else { PFX_TRAIL_RT = (PFX_TRAIL_RT > v) ? PFX_TRAIL_RT : v; }")
                elif conflict == "min":
                    apply.append("          if (!PFX_TRAIL_SET) { PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; } else { PFX_TRAIL_RT = (PFX_TRAIL_RT < v) ? PFX_TRAIL_RT : v; }")
                else:
                    apply.append("          PFX_TRAIL_RT = v; PFX_TRAIL_SET = true; ")
            elif _p == "postfx_bleed":
                # Rules→PostFX bridge: set global bleed amount (0..1) as uint8 0..255.
                apply.append(f"          float vf = clamp01((float)({_arduino_clamp_expr('postfx_bleed', ex)}));")
                apply.append("          uint8_t v = (uint8_t)(vf * 255.0f + 0.5f);")
                if conflict == "first":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; }")
                elif conflict == "max":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; } else { PFX_BLEED_RT = (PFX_BLEED_RT > v) ? PFX_BLEED_RT : v; }")
                elif conflict == "min":
                    apply.append("          if (!PFX_BLEED_SET) { PFX_BLEED_RT = v; PFX_BLEED_SET = true; } else { PFX_BLEED_RT = (PFX_BLEED_RT < v) ? PFX_BLEED_RT : v; }")
                else:
                    apply.append("          PFX_BLEED_RT = v; PFX_BLEED_SET = true; ")
            elif _p == "postfx_bleed_radius":
                # Rules→PostFX bridge: set global bleed radius (1..2).
                apply.append(f"          float vf = (float)({_arduino_clamp_expr('postfx_bleed_radius', ex)});")
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
                apply.append(f"          float v = clamp01((float)({_arduino_clamp_expr('layer_opacity', ex)}));")
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


def _runtime_state_h() -> str:
    """Inline Arduino state runtime (single-file export)."""
    return """// ---- Modulo Stateful Runtime (Phase 5S: Generic State Slots) ----
typedef struct {
  uint32_t reserved;
} EffectState;

// Generic per-layer state slots (for deterministic stateful effects)
// - 4 float slots + 4 int slots per layer
// - ST_INIT marks whether a layer has been initialized for its behavior
static float   ST_F[LAYERS][4];
static int16_t ST_I[LAYERS][4];
static uint8_t ST_INIT[LAYERS];

static inline void state_reset_layer(int li){
  for(int k=0;k<4;k++){ ST_F[li][k]=0.0f; ST_I[li][k]=0; }
  ST_INIT[li]=1;
}

"""


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


class ExportValidationError(Exception):
    pass


# --- LED backend implementation blocks (filled into @@LED_IMPL@@) ---

FASTLED_LED_IMPL = r"""// Modulo export: """ + EXPORT_MARKER + r"""\n// Safe defaults for FastLED template params
#ifndef LED_TYPE
  #define LED_TYPE WS2812B
#endif
#ifndef COLOR_ORDER
  #define COLOR_ORDER GRB
#endif
#ifndef LED_BRIGHTNESS
  #define LED_BRIGHTNESS @@LED_BRIGHTNESS@@
#endif
#include <FastLED.h>
#include <string.h>
CRGB leds[NUM_LEDS];

static void modulo_wifi_init() {
    // Choose credentials: exported constants win; otherwise use stored device creds.
    String ssid = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_SSID) : __modulo_load_ssid();
    String pass = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_PASS) : __modulo_load_pass();

    bool have_creds = (ssid.length() > 0);
    if (have_creds) {
      WiFi.mode(WIFI_STA);
      WiFi.begin(ssid.c_str(), pass.c_str());
      unsigned long t0 = millis();
      while (WiFi.status() != WL_CONNECTED && (millis() - t0) < 15000UL) {
        delay(50);
      }
    }

    if (WiFi.status() == WL_CONNECTED) {
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        if (MDNS.begin(MODULO_WIFI_HOST)) {
          MDNS.addService("http", "tcp", 80);
        }
      }
      __modulo_http_setup();
      __modulo_ntp_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi connected");
      Serial.print("[Modulo] IP: "); Serial.println(WiFi.localIP());
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        Serial.print("[Modulo] mDNS: http://");
        Serial.print(MODULO_WIFI_HOST);
        Serial.println(".local/");
      }
      Serial.println("[Modulo] Web update: http://<ip>/ (upload .bin)");
      Serial.println("[Modulo] Info: http://<ip>/info");
      return;
    }

    // If WiFi is enabled but we couldn't connect, optionally start a setup AP.
    if (MODULO_WIFI_AP_FALLBACK) {
      String base = (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) ? String(MODULO_WIFI_HOST) : String("modulo-hub75");
      String ap_ssid = base + String("-setup");
      const char* ap_pass = (strlen(MODULO_WIFI_AP_PASSWORD) >= 8) ? MODULO_WIFI_AP_PASSWORD : nullptr; // ESP32 requires >=8 or open
      WiFi.mode(WIFI_AP);
      if (ap_pass) WiFi.softAP(ap_ssid.c_str(), ap_pass);
      else WiFi.softAP(ap_ssid.c_str());

      __modulo_http_setup();
      __modulo_ntp_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi not connected; started setup AP");
      Serial.print("[Modulo] AP SSID: "); Serial.println(ap_ssid);
      if (ap_pass) Serial.println("[Modulo] AP password: (set in export)");
      else Serial.println("[Modulo] AP password: (open)");
      Serial.println("[Modulo] Setup: http://192.168.4.1/wifi");
      Serial.println("[Modulo] Web update: http://192.168.4.1/");
    }
  }

  static void modulo_wifi_tick() {}

static void modulo_led_init() {
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(LED_BRIGHTNESS);
}

static void modulo_led_show() {
  FastLED.show();
}

"""


NEOPIXELBUS_LED_IMPL_ESP32 = r"""#include <NeoPixelBus.h>

// Provide a minimal CRGB-compatible type so the generated effect code (and PostFX) can stay unchanged.
struct CRGB {
  uint8_t r, g, b;
  CRGB() : r(0), g(0), b(0) {}
  CRGB(uint8_t R, uint8_t G, uint8_t B) : r(R), g(G), b(B) {}
};

CRGB leds[NUM_LEDS];

static void modulo_wifi_init() {
    // Choose credentials: exported constants win; otherwise use stored device creds.
    String ssid = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_SSID) : __modulo_load_ssid();
    String pass = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_PASS) : __modulo_load_pass();

    bool have_creds = (ssid.length() > 0);
    if (have_creds) {
      WiFi.mode(WIFI_STA);
      WiFi.begin(ssid.c_str(), pass.c_str());
      unsigned long t0 = millis();
      while (WiFi.status() != WL_CONNECTED && (millis() - t0) < 15000UL) {
        delay(50);
      }
    }

    if (WiFi.status() == WL_CONNECTED) {
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        if (MDNS.begin(MODULO_WIFI_HOST)) {
          MDNS.addService("http", "tcp", 80);
        }
      }
      __modulo_http_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi connected");
      Serial.print("[Modulo] IP: "); Serial.println(WiFi.localIP());
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        Serial.print("[Modulo] mDNS: http://");
        Serial.print(MODULO_WIFI_HOST);
        Serial.println(".local/");
      }
      Serial.println("[Modulo] Web update: http://<ip>/ (upload .bin)");
      Serial.println("[Modulo] Info: http://<ip>/info");
      return;
    }

    // If WiFi is enabled but we couldn't connect, optionally start a setup AP.
    if (MODULO_WIFI_AP_FALLBACK) {
      String base = (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) ? String(MODULO_WIFI_HOST) : String("modulo-hub75");
      String ap_ssid = base + String("-setup");
      const char* ap_pass = (strlen(MODULO_WIFI_AP_PASSWORD) >= 8) ? MODULO_WIFI_AP_PASSWORD : nullptr; // ESP32 requires >=8 or open
      WiFi.mode(WIFI_AP);
      if (ap_pass) WiFi.softAP(ap_ssid.c_str(), ap_pass);
      else WiFi.softAP(ap_ssid.c_str());

      __modulo_http_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi not connected; started setup AP");
      Serial.print("[Modulo] AP SSID: "); Serial.println(ap_ssid);
      if (ap_pass) Serial.println("[Modulo] AP password: (set in export)");
      else Serial.println("[Modulo] AP password: (open)");
      Serial.println("[Modulo] Setup: http://192.168.4.1/wifi");
      Serial.println("[Modulo] Web update: http://192.168.4.1/");
    }
  }

  static void modulo_wifi_tick() {}

// WS2812/SK6812 class using ESP32 RMT.
// NOTE: For simplicity, this backend assumes GRB order (NeoGrbFeature).
NeoPixelBus<NeoGrbFeature, NeoEsp32Rmt0800KHzMethod> strip(NUM_LEDS, LED_PIN);

static void modulo_led_init() {
  strip.Begin();
  strip.Show();
}

static void modulo_led_show() {
  for (int i = 0; i < NUM_LEDS; i++) {
#ifdef MATRIX_WIDTH
    int j = (int)modulo_map_index((uint16_t)i);
#else
    int j = i;
#endif
    strip.SetPixelColor(j, RgbColor(leds[i].r, leds[i].g, leds[i].b));
  }
  strip.Show();
}

"""


HUB75_LED_IMPL_ESP32 = r"""// Modulo export: """ + EXPORT_MARKER + r"""\n/*\n  HUB75 CONFIG SUMMARY (autogenerated)\n  backend: @@HUB75_BACKEND_VERSION@@\n  panel: @@HUB75_PANEL_RES_X@@x@@HUB75_PANEL_RES_Y@@   chain: @@HUB75_CHAIN@@\n  brightness: @@HUB75_BRIGHTNESS@@   color_order: @@HUB75_COLOR_ORDER@@   gamma: @@HUB75_USE_GAMMA@@ (@@HUB75_GAMMA@@)\n  matrix: @@MATRIX_WIDTH@@x@@MATRIX_HEIGHT@@   rotate: @@MATRIX_ROTATE@@   flip_x: @@MATRIX_FLIP_X@@   flip_y: @@MATRIX_FLIP_Y@@\n  debug_mode: HUB75_DEBUG_MODE (0=off,1=gradient,2=corners)\n*/\n
// HUB75 (ESP32) - MatrixPanel I2S DMA output
// Library: ESP32-HUB75-MatrixPanel-I2S-DMA (MatrixPanel_I2S_DMA)
//
// NOTE: This backend is export-only. It retains a FastLED-style CRGB buffer
// so Modulo-generated effect code remains unchanged.

#ifndef HUB75_PANEL_RES_X
  #define HUB75_PANEL_RES_X @@HUB75_PANEL_RES_X@@
#endif
#ifndef HUB75_PANEL_RES_Y
  #define HUB75_PANEL_RES_Y @@HUB75_PANEL_RES_Y@@
#endif
#ifndef HUB75_CHAIN
  #define HUB75_CHAIN @@HUB75_CHAIN@@
#endif

#ifndef HUB75_NUM_ROWS
  #define HUB75_NUM_ROWS @@HUB75_NUM_ROWS@@
#endif
#ifndef HUB75_NUM_COLS
  #define HUB75_NUM_COLS @@HUB75_NUM_COLS@@
#endif
#ifndef HUB75_VIRTUAL_CHAIN_TYPE
  // See library docs / ChainedPanels example
  // CHAIN_TOP_LEFT_DOWN etc.
  #define HUB75_VIRTUAL_CHAIN_TYPE @@HUB75_VIRTUAL_CHAIN_TYPE@@
#endif

#ifndef HUB75_BRIGHTNESS
  #define HUB75_BRIGHTNESS @@HUB75_BRIGHTNESS@@
#endif

// Optional gamma correction (applied on output)
// 0 = off, 1 = on
#ifndef HUB75_USE_GAMMA
  #define HUB75_USE_GAMMA @@HUB75_USE_GAMMA@@
#endif
#ifndef HUB75_GAMMA
  #define HUB75_GAMMA @@HUB75_GAMMA@@
#endif

#ifndef HUB75_COLOR_ORDER
  // 0=RGB,1=GRB,2=BRG,3=RBG,4=GBR,5=BGR
  #define HUB75_COLOR_ORDER @@HUB75_COLOR_ORDER@@
#endif

// Serial banner (optional) for quick sanity checks
#ifndef HUB75_SERIAL_BANNER
  #define HUB75_SERIAL_BANNER 1
#endif
#ifndef HUB75_SERIAL_BAUD
  #define HUB75_SERIAL_BAUD 115200
#endif

// Debug output mode (compile-time)
// 0 = normal Modulo output
// 1 = moving gradient
// 2 = corner markers + axis guides
#ifndef HUB75_DEBUG_TESTPATTERN
  // legacy: kept for compatibility with older generated sketches
  #define HUB75_DEBUG_TESTPATTERN 0
#endif
#ifndef HUB75_DEBUG_MODE
  #if HUB75_DEBUG_TESTPATTERN
    #define HUB75_DEBUG_MODE 1
  #else
    #define HUB75_DEBUG_MODE 0
  #endif
#endif

#include <FastLED.h>
#include <string.h>
#include <math.h>

#ifndef MODULO_WIFI_ENABLE
  #define MODULO_WIFI_ENABLE @@WIFI_ENABLE@@
#endif
#ifndef MODULO_WIFI_AP_FALLBACK
  #define MODULO_WIFI_AP_FALLBACK @@WIFI_AP_FALLBACK@@
#endif
#ifndef MODULO_WIFI_AP_PASSWORD
  #define MODULO_WIFI_AP_PASSWORD "@@WIFI_AP_PASSWORD@@"
#endif
#ifndef MODULO_NTP_ENABLE
  #define MODULO_NTP_ENABLE @@WIFI_NTP_ENABLE@@
#endif
#ifndef MODULO_TZ
  #define MODULO_TZ "@@WIFI_TZ@@"
#endif
#ifndef MODULO_NTP1
  #define MODULO_NTP1 "@@WIFI_NTP1@@"
#endif
#ifndef MODULO_NTP2
  #define MODULO_NTP2 "@@WIFI_NTP2@@"
#endif

#if MODULO_WIFI_ENABLE
  #include <WiFi.h>
  #include <WebServer.h>
  #include <Update.h>
  #include <ESPmDNS.h>
  #include <Preferences.h>
  #include <time.h>
  static const char* MODULO_WIFI_SSID = "@@WIFI_SSID@@";
  static const char* MODULO_WIFI_PASS = "@@WIFI_PASSWORD@@";
  static const char* MODULO_WIFI_HOST = "@@WIFI_HOSTNAME@@";
  static WebServer __modulo_server(80);

  static Preferences __modulo_prefs;

  static String __modulo_load_ssid() {
    __modulo_prefs.begin("modulo", true);
    String s = __modulo_prefs.getString("ssid", "");
    __modulo_prefs.end();
    return s;
  }
  static String __modulo_load_pass() {
    __modulo_prefs.begin("modulo", true);
    String s = __modulo_prefs.getString("pass", "");
    __modulo_prefs.end();
    return s;
  }
  static void __modulo_save_creds(const String& ssid, const String& pass) {
    __modulo_prefs.begin("modulo", false);
    __modulo_prefs.putString("ssid", ssid);
    __modulo_prefs.putString("pass", pass);
    __modulo_prefs.end();
  }

  
  static void __modulo_ntp_setup() {
    if (!MODULO_NTP_ENABLE) return;
    const char* tz = (MODULO_TZ && MODULO_TZ[0]) ? MODULO_TZ : "UTC0";
    const char* s1 = (MODULO_NTP1 && MODULO_NTP1[0]) ? MODULO_NTP1 : "pool.ntp.org";
    const char* s2 = (MODULO_NTP2 && MODULO_NTP2[0]) ? MODULO_NTP2 : "time.nist.gov";
    configTzTime(tz, s1, s2, "time.google.com");
    // Try to fetch time quickly (non-fatal if it fails)
    struct tm tm_info;
    if (getLocalTime(&tm_info, 2000)) {
      char buf[64];
      strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm_info);
      Serial.print("[Modulo] NTP time: ");
      Serial.println(buf);
    } else {
      Serial.println("[Modulo] NTP time: (not yet available)");
    }
  }

static void __modulo_http_setup() {
    __modulo_server.on("/", HTTP_GET, []() {
      __modulo_server.send(200, "text/html",
        "<html><head><meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<title>Modulo HUB75 Update</title></head><body>"
        "<h2>Modulo HUB75 Web Update</h2>"
        "<p>Select a compiled .bin and upload.</p>"
        "<form method='POST' action='/update' enctype='multipart/form-data'>"
        "<input type='file' name='update' accept='.bin'/>"
        "<input type='submit' value='Upload'/>"
        "</form>"
        "<p>After success, the device will reboot.</p><p><a href='/wifi'>WiFi setup</a> (save credentials to device)</p>"
        "</body></html>"
      );
    });
__modulo_server.on("/wifi", HTTP_GET, []() {
  String body = "";
  body += "<html><head><meta name='viewport' content='width=device-width, initial-scale=1'/>";
  body += "<title>Modulo WiFi Setup</title></head><body>";
  body += "<h2>Modulo WiFi Setup</h2>";
  body += "<form method='POST' action='/wifi'>";
  body += "SSID:<br/><input name='ssid' length=32/><br/>";
  body += "Password:<br/><input name='pass' type='password' length=64/><br/><br/>";
  body += "<input type='submit' value='Save & Reboot'/>";
  body += "</form>";
  body += "<p><a href='/'>Back</a></p>";
  body += "</body></html>";
  __modulo_server.send(200, "text/html", body);
});

__modulo_server.on("/wifi", HTTP_POST, []() {
  String ssid = __modulo_server.arg("ssid");
  String pass = __modulo_server.arg("pass");
  ssid.trim(); pass.trim();
  if (ssid.length() == 0) {
    __modulo_server.send(400, "text/plain", "SSID required");
    return;
  }
  __modulo_save_creds(ssid, pass);
  __modulo_server.send(200, "text/plain", "Saved. Rebooting...");
  delay(250);
  ESP.restart();
});


    // Simple JSON status endpoint (useful for quick "is it on WiFi?" checks)
    __modulo_server.on("/info", HTTP_GET, []() {
      String ip = WiFi.localIP().toString();
      String hn = (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) ? String(MODULO_WIFI_HOST) : String("");
      String mac = WiFi.macAddress();
      String body = "{";
      body += "\"ok\":true";
      body += ",\"ip\":\"" + ip + "\"";
      body += ",\"hostname\":\"" + hn + "\"";
      body += ",\"mac\":\"" + mac + "\"";
      body += ",\"rssi\":" + String(WiFi.RSSI());
      time_t now = time(nullptr);
      body += ",\"epoch\":" + String((long)now);
      struct tm tm_info;
      if (getLocalTime(&tm_info, 0)) {
        char buf[32];
        strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &tm_info);
        body += ",\"local\":\"" + String(buf) + "\"";
      }

      body += "}";
      __modulo_server.send(200, "application/json", body);
    });

    __modulo_server.on("/update", HTTP_POST,
      []() {
        bool ok = !Update.hasError();
        __modulo_server.send(200, "text/plain", ok ? "OK. Rebooting..." : "FAIL");
        delay(200);
        if (ok) ESP.restart();
      },
      []() {
        HTTPUpload& up = __modulo_server.upload();
        if (up.status == UPLOAD_FILE_START) {
          Update.begin(UPDATE_SIZE_UNKNOWN);
        } else if (up.status == UPLOAD_FILE_WRITE) {
          Update.write(up.buf, up.currentSize);
        } else if (up.status == UPLOAD_FILE_END) {
          Update.end(true);
        }
      }
    );

    __modulo_server.begin();
  }

  static void modulo_wifi_init() {
    if (!MODULO_WIFI_SSID || !MODULO_WIFI_SSID[0]) return; // empty SSID => disabled
    WiFi.mode(WIFI_STA);
    WiFi.begin(MODULO_WIFI_SSID, MODULO_WIFI_PASS);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - t0) < 15000UL) {
      delay(50);
    }
    if (WiFi.status() == WL_CONNECTED) {
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        if (MDNS.begin(MODULO_WIFI_HOST)) {
          MDNS.addService("http", "tcp", 80);
        }
      }
      __modulo_http_setup();

      // Helpful serial output for first-time setup
      Serial.println();
      Serial.println("[Modulo] WiFi connected");
      Serial.print("[Modulo] IP: "); Serial.println(WiFi.localIP());
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        Serial.print("[Modulo] mDNS: http://");
        Serial.print(MODULO_WIFI_HOST);
        Serial.println(".local/");
      }
      Serial.println("[Modulo] Web update: http://<ip>/  (upload .bin)");
      Serial.println("[Modulo] Info: http://<ip>/info");
    }
  }

  static void modulo_wifi_tick() {
    static unsigned long __modulo_last_reconnect = 0;
    if (WiFi.status() == WL_CONNECTED) {
      __modulo_server.handleClient();
      return;
    }
    // Non-blocking reconnect attempt every ~10s
    unsigned long now = millis();
    if ((now - __modulo_last_reconnect) > 10000UL) {
      __modulo_last_reconnect = now;
      if (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) {
        WiFi.disconnect(false);
        WiFi.begin(MODULO_WIFI_SSID, MODULO_WIFI_PASS);
      }
    }
  }
#else
  static void modulo_wifi_init() {
    // Choose credentials: exported constants win; otherwise use stored device creds.
    String ssid = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_SSID) : __modulo_load_ssid();
    String pass = (MODULO_WIFI_SSID && MODULO_WIFI_SSID[0]) ? String(MODULO_WIFI_PASS) : __modulo_load_pass();

    bool have_creds = (ssid.length() > 0);
    if (have_creds) {
      WiFi.mode(WIFI_STA);
      WiFi.begin(ssid.c_str(), pass.c_str());
      unsigned long t0 = millis();
      while (WiFi.status() != WL_CONNECTED && (millis() - t0) < 15000UL) {
        delay(50);
      }
    }

    if (WiFi.status() == WL_CONNECTED) {
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        if (MDNS.begin(MODULO_WIFI_HOST)) {
          MDNS.addService("http", "tcp", 80);
        }
      }
      __modulo_http_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi connected");
      Serial.print("[Modulo] IP: "); Serial.println(WiFi.localIP());
      if (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) {
        Serial.print("[Modulo] mDNS: http://");
        Serial.print(MODULO_WIFI_HOST);
        Serial.println(".local/");
      }
      Serial.println("[Modulo] Web update: http://<ip>/ (upload .bin)");
      Serial.println("[Modulo] Info: http://<ip>/info");
      return;
    }

    // If WiFi is enabled but we couldn't connect, optionally start a setup AP.
    if (MODULO_WIFI_AP_FALLBACK) {
      String base = (MODULO_WIFI_HOST && MODULO_WIFI_HOST[0]) ? String(MODULO_WIFI_HOST) : String("modulo-hub75");
      String ap_ssid = base + String("-setup");
      const char* ap_pass = (strlen(MODULO_WIFI_AP_PASSWORD) >= 8) ? MODULO_WIFI_AP_PASSWORD : nullptr; // ESP32 requires >=8 or open
      WiFi.mode(WIFI_AP);
      if (ap_pass) WiFi.softAP(ap_ssid.c_str(), ap_pass);
      else WiFi.softAP(ap_ssid.c_str());

      __modulo_http_setup();

      Serial.println();
      Serial.println("[Modulo] WiFi not connected; started setup AP");
      Serial.print("[Modulo] AP SSID: "); Serial.println(ap_ssid);
      if (ap_pass) Serial.println("[Modulo] AP password: (set in export)");
      else Serial.println("[Modulo] AP password: (open)");
      Serial.println("[Modulo] Setup: http://192.168.4.1/wifi");
      Serial.println("[Modulo] Web update: http://192.168.4.1/");
    }
  }

    static void modulo_wifi_tick() {}
#endif


#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <ESP32-VirtualMatrixPanel-I2S-DMA.h>

CRGB leds[NUM_LEDS];

static MatrixPanel_I2S_DMA* dma_display = nullptr;
static VirtualMatrixPanel* virtualDisp = nullptr;

static uint8_t hub75_gamma_lut[256];

static void hub75_gamma_init_lut() {
  // Build once at startup; cheap (256 ops) and much faster than per-pixel powf().
#if HUB75_USE_GAMMA
  for (int i = 0; i < 256; i++) {
    float x = (float)i / 255.0f;
    float y = powf(x, (float)HUB75_GAMMA);
    int o = (int)(y * 255.0f + 0.5f);
    if (o < 0) o = 0;
    if (o > 255) o = 255;
    hub75_gamma_lut[i] = (uint8_t)o;
  }
#else
  for (int i = 0; i < 256; i++) hub75_gamma_lut[i] = (uint8_t)i;
#endif
}

static inline void hub75_swizzle(uint8_t &r, uint8_t &g, uint8_t &b) {
#if HUB75_COLOR_ORDER == 0
  // RGB (no-op)
#elif HUB75_COLOR_ORDER == 1
  // GRB
  { uint8_t R=r; r=g; g=R; }
#elif HUB75_COLOR_ORDER == 2
  // BRG
  { uint8_t R=r; uint8_t G=g; uint8_t B=b; r=B; g=R; b=G; }
#elif HUB75_COLOR_ORDER == 3
  // RBG
  { uint8_t G=g; g=b; b=G; }
#elif HUB75_COLOR_ORDER == 4
  // GBR
  { uint8_t R=r; uint8_t G=g; uint8_t B=b; r=G; g=B; b=R; }
#elif HUB75_COLOR_ORDER == 5
  // BGR
  { uint8_t R=r; r=b; b=R; }
#endif
}

static inline uint8_t hub75_gamma_u8(uint8_t v) {
  return hub75_gamma_lut[v];
}

static void modulo_led_init() {
  hub75_gamma_init_lut();

#if HUB75_SERIAL_BANNER
  Serial.begin(HUB75_SERIAL_BAUD);
  Serial.println();
  Serial.println("[Modulo] HUB75 init");
  Serial.print("panel="); Serial.print(HUB75_PANEL_RES_X); Serial.print("x"); Serial.print(HUB75_PANEL_RES_Y);
  Serial.print(" chain="); Serial.print(HUB75_CHAIN);
  Serial.print(" brightness="); Serial.print(HUB75_BRIGHTNESS);
  Serial.print(" color_order="); Serial.print(HUB75_COLOR_ORDER);
  Serial.print(" gamma="); Serial.print((int)HUB75_USE_GAMMA);
#if HUB75_USE_GAMMA
  Serial.print("("); Serial.print((float)HUB75_GAMMA); Serial.print(")");
#endif
  Serial.println();
#ifdef MATRIX_WIDTH
  Serial.print("matrix="); Serial.print(MATRIX_WIDTH); Serial.print("x"); Serial.print(MATRIX_HEIGHT);
#endif
#ifdef MATRIX_ROTATE
  Serial.print(" rotate="); Serial.print(MATRIX_ROTATE);
#endif
#ifdef MATRIX_FLIP_X
  Serial.print(" flip_x="); Serial.print(MATRIX_FLIP_X);
#endif
#ifdef MATRIX_FLIP_Y
  Serial.print(" flip_y="); Serial.print(MATRIX_FLIP_Y);
#endif
  Serial.print(" debug_mode="); Serial.print(HUB75_DEBUG_MODE);
  Serial.println();
#endif

  HUB75_I2S_CFG mxconfig(
    HUB75_PANEL_RES_X,  // module width
    HUB75_PANEL_RES_Y,  // module height
    HUB75_CHAIN         // chain length
  );

  // Safe defaults
  mxconfig.gpio.e = -1;          // many 64x32 panels do not use E
  mxconfig.double_buff = true;   // tear-free updates
  mxconfig.i2sspeed = HUB75_I2S_CFG::HZ_10M; // safe baseline

  dma_display = new MatrixPanel_I2S_DMA(mxconfig);
  dma_display->begin();
  dma_display->setBrightness8((uint8_t)HUB75_BRIGHTNESS);
  dma_display->clearScreen();

  // Optional virtual display for panel grids (NUM_ROWS x NUM_COLS)
  if ((HUB75_NUM_ROWS * HUB75_NUM_COLS) > 1) {
    // create VirtualDisplay object based on our newly created dma_display object
    // Signature (library >=3.0.6): VirtualMatrixPanel((*dma_display), NUM_ROWS, NUM_COLS, PANEL_RES_X, PANEL_RES_Y, VIRTUAL_MATRIX_CHAIN_TYPE)
    virtualDisp = new VirtualMatrixPanel((*dma_display), HUB75_NUM_ROWS, HUB75_NUM_COLS, HUB75_PANEL_RES_X, HUB75_PANEL_RES_Y, HUB75_VIRTUAL_CHAIN_TYPE);
  }
}

static void modulo_led_show() {
  if (!dma_display) return;

#if HUB75_DEBUG_MODE == 1
  // Moving gradient test pattern to validate mapping/orientation quickly.
  static uint32_t _hub75_dbg_frame = 0;
  _hub75_dbg_frame++;
  const uint16_t w = (uint16_t)MATRIX_WIDTH;
  const uint16_t h = (uint16_t)MATRIX_HEIGHT;
  const uint16_t wm1 = (w > 1) ? (uint16_t)(w - 1) : 1;
  const uint16_t hm1 = (h > 1) ? (uint16_t)(h - 1) : 1;
  for (uint16_t y = 0; y < h; y++) {
    for (uint16_t x = 0; x < w; x++) {
      uint8_t r = (uint8_t)((uint32_t)x * 255u / wm1);
      uint8_t g = (uint8_t)((uint32_t)y * 255u / hm1);
      uint8_t b = (uint8_t)((_hub75_dbg_frame >> 2) + x + y);
      uint16_t i = (uint16_t)(y * w + x);
      if (i < (uint16_t)NUM_LEDS) {
        leds[i].r = r;
        leds[i].g = g;
        leds[i].b = b;
      }
    }
  }
#elif HUB75_DEBUG_MODE == 2
  // Corner markers + axis guides:
  // TL=Red, TR=Green, BL=Blue, BR=White; plus faint X/Y axis lines.
  const uint16_t w = (uint16_t)MATRIX_WIDTH;
  const uint16_t h = (uint16_t)MATRIX_HEIGHT;
  const uint16_t n = (uint16_t)(w * h);
  // Clear buffer
  for (uint16_t i = 0; i < n && i < (uint16_t)NUM_LEDS; i++) leds[i] = CRGB(0,0,0);

  auto set_xy = [&](uint16_t x, uint16_t y, uint8_t r, uint8_t g, uint8_t b) {
    if (x >= w || y >= h) return;
    uint16_t i = (uint16_t)(y * w + x);
    if (i < (uint16_t)NUM_LEDS) { leds[i].r=r; leds[i].g=g; leds[i].b=b; }
  };

  // Corners
  set_xy(0, 0, 255, 0, 0);
  set_xy((w > 0) ? (uint16_t)(w - 1) : 0, 0, 0, 255, 0);
  set_xy(0, (h > 0) ? (uint16_t)(h - 1) : 0, 0, 0, 255);
  set_xy((w > 0) ? (uint16_t)(w - 1) : 0, (h > 0) ? (uint16_t)(h - 1) : 0, 255, 255, 255);

  // Axis guides (dim)
  for (uint16_t x = 0; x < w; x++) set_xy(x, 0, 64, 0, 0);
  for (uint16_t y = 0; y < h; y++) set_xy(0, y, 0, 0, 64);
#endif

#ifdef MATRIX_WIDTH
  // Map logical -> physical using Modulo's origin/serpentine/rotate/flip mapping.
  const uint16_t w = (uint16_t)MATRIX_WIDTH;
  const uint16_t h = (uint16_t)MATRIX_HEIGHT;
  const uint16_t n = (uint16_t)(w * h);
  for (uint16_t i = 0; i < n && i < (uint16_t)NUM_LEDS; i++) {
    uint16_t j = (uint16_t)modulo_map_index(i);
    uint16_t x = (uint16_t)(j % w);
    uint16_t y = (uint16_t)(j / w);

    CRGB c = leds[i];
    uint8_t r = hub75_gamma_u8(c.r);
    uint8_t g = hub75_gamma_u8(c.g);
    uint8_t b = hub75_gamma_u8(c.b);
    hub75_swizzle(r, g, b);

    if (virtualDisp) virtualDisp->drawPixelRGB888((int)x, (int)y, (int)r, (int)g, (int)b);
    else dma_display->drawPixelRGB888((int)x, (int)y, (int)r, (int)g, (int)b);
  }
#else
  // Strip-like fallback: render as 1-row
  for (uint16_t i = 0; i < (uint16_t)NUM_LEDS; i++) {
    CRGB c = leds[i];
    uint8_t r = hub75_gamma_u8(c.r);
    uint8_t g = hub75_gamma_u8(c.g);
    uint8_t b = hub75_gamma_u8(c.b);
    hub75_swizzle(r, g, b);
    if (virtualDisp) virtualDisp->drawPixelRGB888((int)i, 0, (int)r, (int)g, (int)b);
    else dma_display->drawPixelRGB888((int)i, 0, (int)r, (int)g, (int)b);
  }
#endif
  // With I2S-DMA, draws are pushed as you write; no FastLED.show().
}

"""

def validate_export_text(text: str) -> None:
    """
    Fail-closed exporter validation.

    - No unresolved @@TOKENS@@
    - No accidental python placeholders from UI/engine (e.g. {engine., {len()
    - No accidental double-brace artifacts ({{ or }})
    - Must include EXPORT_MARKER marker
    - Must include required defs markers
    """
    tokens = TOKEN_RE.findall(text)
    if tokens:
        raise ExportValidationError(f"Unresolved tokens found: {tokens}")

    for bad in ("{engine.", "{len("):
        if bad in text:
            raise ExportValidationError(f"Forbidden artifact found in export: {bad}")

    # Prove which exporter produced this .ino
    if EXPORT_MARKER not in text:
        raise ExportValidationError("Export missing EXPORT_MARKER marker")

    required_markers = [
        "state_reset_layer",
    ]
    missing = [m for m in required_markers if m not in text]
    if missing:
        raise ExportValidationError(f"Export missing required definitions: {missing}")

def export_sketch(*, sketch_code: str, template_path: Path, out_path: Path, replacements: dict | None = None) -> Path:
    """Write a sketch file by filling a token template.

    Token format is @@TOKEN@@.
    Always replaces @@SKETCH@@. Optional `replacements` can fill additional tokens.
    """
    tpl = Path(template_path).read_text(encoding="utf-8", errors="ignore")
    out = tpl.replace("@@SKETCH@@", str(sketch_code).rstrip() + "\n")

    if replacements:
        # Replace in a deterministic order for easier debugging.
        # Multi-pass so tokens introduced by expansions (e.g. LED_IMPL blocks) get replaced too.
        for _pass in range(3):
            changed = False
            for k in sorted(replacements.keys()):
                token = f"@@{k}@@"
                v = str(replacements[k])
                if token in out:
                    out2 = out.replace(token, v)
                    if out2 != out:
                        changed = True
                        out = out2
            if not changed:
                break
    validate_export_text(out)
    Path(out_path).write_text(out, encoding="utf-8")
    return Path(out_path)

def make_solid_sketch(*, num_leds: int, led_pin: int, rgb: Tuple[int,int,int]) -> str:
    r,g,b = (int(rgb[0])&255, int(rgb[1])&255, int(rgb[2])&255)
    sketch = """/ Generated by Modulo
#include <FastLED.h>
#include <string.h>

// Debug option: print purpose channels over Serial
#define DBG_PURPOSE_SERIAL {1 if DBG_PURPOSE else 0}
#define DBG_SERIAL_BAUD {DBG_BAUD}

#define NUM_LEDS {num_leds}
// Wiring / LED config (filled by export target; defaults come from Export tab)
#define LED_PIN @@DATA_PIN@@
#define LED_TYPE @@LED_TYPE@@
#define COLOR_ORDER @@COLOR_ORDER@@
#define LED_BRIGHTNESS @@LED_BRIGHTNESS@@
CRGB leds[NUM_LEDS];

void setup() {{
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(255);
}}

void loop() {{

  // --- Fixed-step updates for stateful behaviors (deterministic) ---
  if (__last_ms == 0) __last_ms = now;
  unsigned long __elapsed_ms = now - __last_ms;
  __last_ms = now;
  __accum_s += (float)__elapsed_ms / 1000.0f;

  int __steps = 0;
  while (__accum_s >= __FIXED_DT && __steps < 4) {
    __accum_s -= __FIXED_DT;
    __steps++;

    for (int li=0; li<LAYERS; li++) {
      float br, sp, wd, so, dn, dir;
      float pf0=0.0f, pf1=0.0f, pf2=0.0f, pf3=0.0f;
      float pi0=0.0f, pi1=0.0f, pi2=0.0f, pi3=0.0f;
      computeLayerParams(li, t, br, sp, wd, so, dn, dir, pf0, pf1, pf2, pf3, pi0, pi1, pi2, pi3);

      uint8_t beh = L_BEH[li];
      if (beh == 9) updateBreakout(li, __FIXED_DT, sp, wd, so, dn, pf0);
      else if (beh == 10) updateAsteroids(li, __FIXED_DT, sp, so, dn, pf0, pf1, pi0);
      else if (beh == 14) updateSnakeLite(li, __FIXED_DT, sp, pf0, pf1, pi0);
      else if (beh == 15) updateInvadersLite(li, __FIXED_DT, sp, pf0, pf1, pi0);
      else if (beh == 16) updateShooterLite(li, __FIXED_DT, sp, pf0, pf1, pi0);
      else if (beh == 17) updateBlocksBallLite(li, __FIXED_DT, sp, pf0, pf1, pi0);
    }
  }

  for (int i=0; i<NUM_LEDS; i++) {{
    leds[i] = CRGB({r},{g},{b});
  }}
  FastLED.show();
  delay(10);
}}

"""
    sketch = sketch.replace("{1 if DBG_PURPOSE else 0}", str(1 if DBG_PURPOSE else 0))
    sketch = sketch.replace("{DBG_BAUD}", str(DBG_BAUD))
    sketch = sketch.replace("{num_leds}", str(num_leds))
    sketch = sketch.replace("{int(num_leds)}", str(int(num_leds)))
    sketch = sketch.replace("{int(led_pin)}", str(int(led_pin)))
    return sketch


def _validate_layers_for_export(layers: List[Dict[str, Any]]):
    if not layers:
        raise ExportValidationError("No layers to export.")
    for i, L in enumerate(layers):
        if str(L.get("behavior","")) != "solid":
            raise ExportValidationError(f"Layer {i+1}: only 'solid' is exportable in Phase 3D.")
        # modulotors: we support at most one enabled brightness lfo_sine per layer
        mods = L.get("modulotors", []) or []
        enabled = [m for m in mods if m.get("enabled")]
        for m in enabled:
            if m.get("target") != "brightness":
                raise ExportValidationError(f"Layer {i+1}: only brightness modulotion is exportable in Phase 3D.")
            if m.get("source") != "lfo_sine":
                raise ExportValidationError(f"Layer {i+1}: only lfo_sine modulotion is exportable in Phase 3D.")
            if m.get("mode") not in ("add","mul","set"):
                raise ExportValidationError(f"Layer {i+1}: unsupported mode {m.get('mode')}.")

def make_solid_layers_sketch(*, num_leds: int, led_pin: int, layers: List[Dict[str, Any]]) -> str:
    """Export for multiple SOLID layers with opacity + optional LFO brightness modulotion.

    Notes:
    - In Phase 3D, only 'solid' layers are exportable.
    - Each layer may have 0..1 enabled brightness modulotor using lfo_sine.
    """
    _validate_layers_for_export(layers)

    # emit layer constants arrays
    max_layers = 8
    if len(layers) > max_layers:
        raise ExportValidationError(f"Too many layers for Phase 3D export (max {max_layers}).")

    def clamp01(x):
        try: x = float(x)
        except Exception: x = 0.0
        return 0.0 if x < 0 else (1.0 if x > 1.0 else x)

    # Prepare lists
    lr, lg, lb, lop, lbr, lblend = [], [], [], [], [], []
    ltgt_kind, ltgt_ref = [], []
    lfo_on, lfo_mode, lfo_amt, lfo_hz = [], [], [], []
    for L in layers:
        c = L.get("color",(255,0,0))
        r,g,b = int(c[0])&255, int(c[1])&255, int(c[2])&255
        br = clamp01(L.get("brightness", 1.0))
        op = clamp01(L.get("opacity", 1.0))
        lr.append(r); lg.append(g); lb.append(b); lbr.append(br); lop.append(op)
        bm = str(L.get('blend_mode','over')).lower().strip()
        bm_id = 0
        if bm == 'add': bm_id = 1
        elif bm == 'max': bm_id = 2
        elif bm == 'multiply': bm_id = 3
        elif bm == 'screen': bm_id = 4
        lblend.append(bm_id)
        tk = str(L.get('target_kind','all')).lower().strip()
        tid = 0
        if tk == 'group': tid = 1
        elif tk == 'zone': tid = 2
        ltgt_kind.append(tid)
        ltgt_ref.append(int(L.get('target_ref',0)))

        # find first enabled mod
        mods = L.get("modulotors", []) or []
        m = next((m for m in mods if m.get("enabled")), None)
        if m is None:
            lfo_on.append(0); lfo_mode.append(0); lfo_amt.append(0.0); lfo_hz.append(0.0)
        else:
            lfo_on.append(1)
            mode = str(m.get("mode","mul"))
            mode_id = 1 if mode=="add" else (2 if mode=="set" else 0)  # 0=mul,1=add,2=set
            lfo_mode.append(mode_id)
            lfo_amt.append(float(m.get("amount", 0.5)))
            lfo_hz.append(float(m.get("rate_hz", 0.5)))

    # Convert python floats to C literals
    def f(x): 
        return ("%.6ff" % float(x))
    lr_s = ",".join(str(x) for x in lr)
    lg_s = ",".join(str(x) for x in lg)
    lb_s = ",".join(str(x) for x in lb)
    lop_s = ",".join(f(x) for x in lop)
    lbr_s = ",".join(f(x) for x in lbr)
    lblend_s = ",".join(str(x) for x in lblend)
    ltgt_kind_s = ",".join(str(x) for x in ltgt_kind)
    ltgt_ref_s = ",".join(str(x) for x in ltgt_ref)
    lfo_on_s = ",".join(str(x) for x in lfo_on)
    lfo_mode_s = ",".join(str(x) for x in lfo_mode)
    lfo_amt_s = ",".join(f(x) for x in lfo_amt)
    lfo_hz_s = ",".join(f(x) for x in lfo_hz)

    nL = len(layers)

    return """/ Generated by Modulo (Phase 3D: Multi-layer Solid + LFO brightness)
#include <FastLED.h>
#include <string.h>

// Debug option: print purpose channels over Serial
#define DBG_PURPOSE_SERIAL {1 if DBG_PURPOSE else 0}
#define DBG_SERIAL_BAUD {DBG_BAUD}
#include <math.h>

#define NUM_LEDS {int(num_leds)}
#define LED_PIN {int(led_pin)}
#define LAYERS {nL}

CRGB leds[NUM_LEDS];

const uint8_t L_R[LAYERS] = {{{lr_s}}};
const uint8_t L_G[LAYERS] = {{{lg_s}}};
const uint8_t L_B[LAYERS] = {{{lb_s}}};
const float   L_OP[LAYERS] = {{{lop_s}}};
const float   L_BR[LAYERS] = {{{lbr_s}}};
const uint8_t L_BLEND[LAYERS] = {{{lblend_s}}}; // 0=over,1=add,2=max,3=multiply,4=screen
const uint8_t L_TGT_KIND[LAYERS] = {{{ltgt_kind_s}}}; // 0=all,1=group,2=zone
const int16_t L_TGT_REF[LAYERS] = {{{ltgt_ref_s}}};

// Groups/Zones payload (may be empty)
const uint16_t GROUP_COUNT = @@GROUP_COUNT@@;
const uint16_t ZONE_COUNT  = @@ZONE_COUNT@@;
const uint16_t GROUP_OFFS[GROUP_COUNT] = @@GROUP_OFFS@@;
const uint16_t GROUP_LENS[GROUP_COUNT] = @@GROUP_LENS@@;
const uint16_t GROUP_INDEXES[@@GROUP_INDEXES_LEN@@] = @@GROUP_INDEXES@@;
const int16_t  ZONE_START[ZONE_COUNT] = @@ZONE_START@@;
const int16_t  ZONE_END[ZONE_COUNT]   = @@ZONE_END@@;

// LFO brightness modulotion per layer (optional)
const uint8_t LFO_ON[LAYERS] = {{{lfo_on_s}}};   // 0/1
const uint8_t LFO_MODE[LAYERS] = {{{lfo_mode_s}}}; // 0=mul,1=add,2=set
const float   LFO_AMT[LAYERS] = {{{lfo_amt_s}}};
const float   LFO_HZ[LAYERS] = {{{lfo_hz_s}}};

static inline float clamp01(float x) {{
  if (x < 0.0f) return 0.0f;
  if (x > 1.0f) return 1.0f;
  return x;
}}

static inline float applyMode(float base, float sig, uint8_t mode, float amt) {{
  if (mode == 1) return base + sig * amt;       // add
  if (mode == 2) return sig * amt;             // set
  return base * (1.0f + sig * amt);            // mul
}}

void setup() {{
  if (DBG_PURPOSE_SERIAL) {{
    Serial.begin(DBG_SERIAL_BAUD);
    delay(10);
  }}
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(255);
}}

void loop() {{
  // time in seconds
  float t = (float)millis() / 1000.0f;

  // Compute final composite color once (solid layers)
  float outR = 0.0f, outG = 0.0f, outB = 0.0f;

  for (int li = 0; li < LAYERS; li++) {{
    float br = L_BR[li];

    if (LFO_ON[li]) {{
      float sig = sinf(2.0f * 3.1415926f * LFO_HZ[li] * t); // [-1..1]
      br = applyMode(br, sig, LFO_MODE[li], LFO_AMT[li]);
    }}
    br = clamp01(br);

    float layerR = ((float)L_R[li]) * br;
    float layerG = ((float)L_G[li]) * br;
    float layerB = ((float)L_B[li]) * br;

    float op = clamp01(L_OP[li]);

    float blendedR = blendChan(outR, layerR, L_BLEND[li]);
    float blendedG = blendChan(outG, layerG, L_BLEND[li]);
    float blendedB = blendChan(outB, layerB, L_BLEND[li]);

    outR = outR * (1.0f - op) + blendedR * op;
    outG = outG * (1.0f - op) + blendedG * op;
    outB = outB * (1.0f - op) + blendedB * op;
  }}

  uint8_t r = (uint8_t)constrain((int)(outR + 0.5f), 0, 255);
  uint8_t g = (uint8_t)constrain((int)(outG + 0.5f), 0, 255);
  uint8_t b = (uint8_t)constrain((int)(outB + 0.5f), 0, 255);

  for (int i=0; i<NUM_LEDS; i++) {{
    leds[i] = CRGB(r,g,b);
  }}
  FastLED.show();
  delay(10);
}}

"""


def apply_audio_export_config(sketch: str, cfg: dict) -> str:
    if not isinstance(cfg, dict):
        return sketch
    use = bool(cfg.get("use_spectrum_shield", True))
    reset = cfg.get("reset_pin", 5)
    strobe = cfg.get("strobe_pin", 4)
    left = cfg.get("left_pin", "A0")
    right = cfg.get("right_pin", "A1")

    def _rep(pattern: str, repl: str) -> str:
        return re.sub(pattern, repl, sketch)

    sketch = _rep(r"#define\s+MODULA_USE_SPECTRUM_SHIELD\s+\d+", f"#define MODULA_USE_SPECTRUM_SHIELD {1 if use else 0}")
    sketch = _rep(r"#define\s+MSGEQ7_RESET_PIN\s+\S+", f"#define MSGEQ7_RESET_PIN {int(reset)}")
    sketch = _rep(r"#define\s+MSGEQ7_STROBE_PIN\s+\S+", f"#define MSGEQ7_STROBE_PIN {int(strobe)}")
    sketch = _rep(r"#define\s+MSGEQ7_LEFT_PIN\s+\S+", f"#define MSGEQ7_LEFT_PIN {left}")
    sketch = _rep(r"#define\s+MSGEQ7_RIGHT_PIN\s+\S+", f"#define MSGEQ7_RIGHT_PIN {right}")
    return sketch

def make_external_audio_streamer_sketch(export_audio_cfg: dict) -> str:
    """Generate an Arduino sketch that streams Spectrum Shield/MSGEQ7 audio to Modulo via Serial."""
    cfg = dict(export_audio_cfg or {})
    reset_pin = int(cfg.get("reset_pin", 5))
    strobe_pin = int(cfg.get("strobe_pin", 4))
    left_pin = str(cfg.get("left_pin", "A0"))
    right_pin = str(cfg.get("right_pin", "A1"))

    tpl_path = Path(__file__).resolve().parent / "arduino_external_audio_streamer.ino.tpl"
    tpl = tpl_path.read_text(encoding="utf-8")

    out = tpl.replace("@@MSGEQ7_RESET_PIN@@", str(reset_pin))              .replace("@@MSGEQ7_STROBE_PIN@@", str(strobe_pin))              .replace("@@MSGEQ7_LEFT_PIN@@", left_pin)              .replace("@@MSGEQ7_RIGHT_PIN@@", right_pin)

    # Validate no unreplaced tokens remain
    validate_export_text(out)
    return out

def make_layerstack_sketch(*, project: dict) -> str:
    """Generate an Arduino sketch that renders a stack of layers (solid/chase/wipe/sparkle/scanner)
    with per-layer opacity, blend_mode, target masks, and basic modulotors (LFO + passthrough for future audio).

    Inputs are project dict matching app export payload.
    """
    layout = project.get("layout", {}) or {}
    expcfg = (project.get("export") or {}) if isinstance(project.get("export"), dict) else {}
    DBG_PURPOSE = bool(expcfg.get("debug_purpose_serial", False))
    try:
        DBG_BAUD = int(expcfg.get("debug_serial_baud", 115200) or 115200)
    except Exception:
        DBG_BAUD = 115200
    # Layout normalization: support both legacy (shape/num_leds) and canonical (kind/width/height)
    layout_kind = str(layout.get("kind") or "").strip().lower()
    shape = str(layout.get("shape") or layout_kind or "strip").strip().lower()
    if shape == "matrix":
        shape = "cells"
    # Matrix dims (canonical)
    mw = int(layout.get("mw", layout.get("width", 16)))
    mh = int(layout.get("mh", layout.get("height", 16)))
    # LED count (canonical matrix uses width*height)
    if shape == "cells" and ("width" in layout or "height" in layout):
        num_leds = int(mw * mh)
    else:
        num_leds = int(layout.get("num_leds", 60))
    led_pin = int(layout.get("led_pin", 6))
    cell = int(layout.get("cell", 14))
    matrix_serp = bool(layout.get("matrix_serpentine", False))
    flip_x = bool(layout.get("matrix_flip_x", False))
    flip_y = bool(layout.get("matrix_flip_y", False))
    rotate = int(layout.get("matrix_rotate", 0))
    rotate = rotate if rotate in (0,90,180,270) else 0

    postfx_decls, postfx_apply = _emit_postfx_blocks(project=project, shape=shape, num_leds=num_leds)
    rules_decls, rules_apply = _emit_rules_v6_blocks(project=project)


    layers = [
        L for L in list(project.get("layers", []) or [])
        if bool((L or {}).get("enabled", True))
        and ((L or {}).get("behavior") or (L or {}).get("effect")) != "audio_meter"
    ]
    groups = list(project.get("groups", []) or [])
    zones = list(project.get("zones", []) or [])

    # Export targeting truth: apply project-wide UI target mask (including composed masks)
    # by synthesizing groups for resolved index sets and intersecting per-layer targets.
    ui = (project.get("ui") or {}) if isinstance(project.get("ui"), dict) else {}
    ui_target_mask_key = ui.get("target_mask")
    ui_mask_set = set()
    try:
        if isinstance(ui_target_mask_key, str) and ui_target_mask_key.strip():
            ui_mask_set = set(resolve_mask_to_indices(project, ui_target_mask_key, n=num_leds))
    except Exception:
        ui_mask_set = set()

    # Build a map of existing group index sets for dedupe
    _group_sets = []
    _group_set_to_id = {}
    for gi, g in enumerate(list(groups)):
        inds = g.get("indices", []) if isinstance(g, dict) else []
        try:
            fs = frozenset(int(v) for v in (inds or []) if int(v) >= 0 and int(v) < num_leds)
        except Exception:
            fs = frozenset()
        _group_sets.append(fs)
        if fs and fs not in _group_set_to_id:
            _group_set_to_id[fs] = gi

    def _ensure_group_for_set(s: set[int]) -> int:
        fs = frozenset(sorted(int(v) for v in s if 0 <= int(v) < num_leds))
        if not fs:
            return -1
        if fs in _group_set_to_id:
            return int(_group_set_to_id[fs])
        gid = len(groups)
        groups.append({"name": f"export_mask_{gid}", "indices": list(fs)})
        _group_sets.append(fs)
        _group_set_to_id[fs] = gid
        return gid

    def _layer_base_indices(tk_id: int, tref: int) -> set[int]:
        if tk_id == 0:
            return set(range(num_leds))
        if tk_id == 1:
            if 0 <= int(tref) < len(_group_sets):
                return set(_group_sets[int(tref)])
            return set(range(num_leds))
        if tk_id == 2:
            if 0 <= int(tref) < len(zones):
                z = zones[int(tref)]
                try:
                    a = int(z.get("start", 0)); b = int(z.get("end", 0))
                except Exception:
                    return set(range(num_leds))
                if a > b: a, b = b, a
                a = 0 if a < 0 else a
                b = (num_leds-1) if b >= num_leds else b
                return set(range(a, b+1))
            return set(range(num_leds))
        return set(range(num_leds))


    # behavior ids
    beh_map = {"solid":0, "chase":1, "wipe":2, "sparkle":3, "scanner":4, "fade":5, "strobe":6, "rainbow":7, "bouncer":8, "breakout_lite":9, "breakout_game":9, "demo_breakout":9, "asteroids_lite":10, "asteroids_game":10, "demo_asteroids":10, "tilemap_sprite":11, "red_hat_runner":11, "mariobros_clockface":11, "brians_brain":12, "game_of_life":12, "elementary_ca":12, "langtons_ant":12, "msgeq7_visualizer_575":13, "msgeq7_reactive_ino":13, "snake_game":14, "snake_game_ino":14, "space_invaders_game":15, "shooter_game_ino":16, "blocks_ball_game_ino":17}

    def _clamp01(x):
        try:
            x=float(x)
        except Exception:
            x=0.0
        return 0.0 if x<0.0 else (1.0 if x>1.0 else x)

    def _csv(arr):
        return ",".join(str(x) for x in arr)

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

    # Operators runtime (deterministic subset)
    # NOTE: Operators are applied per-layer (pre-blend). Export supports a minimal subset:
    # - gain (scalar multiplier)
    # - gamma (power curve)
    # - posterize (channel quantization)
    OPS_PER_LAYER = 2
    OP_KIND = []   # 0=none,1=gain,2=gamma,3=posterize
    OP_P0 = []     # param0 (gain/gamma/levels)

    OP_KIND_MAP = {
        "none": 0,
        "gain": 1,
        "gamma": 2,
        "posterize": 3,
    }

    # modulotors: flatten up to 2 per layer
    # Source ids: none=0, lfo_sine=1 (audio placeholders: 10+)
    SRC = {"none":0, "lfo_sine":1, "energy":10, "audio_energy":10}
    for i in range(7):
        # normalized keys
        SRC[f"mono{i}"]=11+i
        SRC[f"l{i}"]=21+i
        SRC[f"r{i}"]=31+i
        # legacy aliases
        SRC[f"audio_mono{i}"]=11+i
        SRC[f"audio_L{i}"]=21+i
        SRC[f"audio_R{i}"]=31+i
    # purpose sources (0..1)
    SRC["purpose_f0"]=50; SRC["purpose_f1"]=51; SRC["purpose_f2"]=52; SRC["purpose_f3"]=53
    SRC["purpose_i0"]=54; SRC["purpose_i1"]=55; SRC["purpose_i2"]=56; SRC["purpose_i3"]=57
    CURVE={"linear":0,"invert":1,"abs":2,"pow2":3,"pow3":4}
    MODE={"mul":0,"add":1,"set":2}

    MODS_PER_LAYER=2
    M_SRC=[]; M_TGT=[]; M_MODE=[]; M_AMT=[]; M_RATE=[]; M_BIAS=[]; M_SMOOTH=[]; M_CURVE=[]; M_PHASE=[]
    # target param id mapping for modulotors
    tgt_map={"brightness":0,"speed":1,"width":2,"softness":3,"density":4,"direction":5,"purpose_f0":6,"purpose_f1":7,"purpose_f2":8,"purpose_f3":9,"purpose_i0":10,"purpose_i1":11,"purpose_i2":12,"purpose_i3":13}

    for L in layers:
        beh = str(L.get("behavior","solid")).lower().strip()
        beh_id = beh_map.get(beh, 7)
        L_BEH.append(beh_id)

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
        elif beh == 'msgeq7_visualizer_575':
            params = dict(params)
            params.setdefault('pi0', 0)
            params.setdefault('pf1', 1.0)  # gain
        elif beh == 'msgeq7_reactive_ino':
            params = dict(params)
            params.setdefault('pi0', 1)
            params.setdefault('pf1', 1.0)  # gain

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

        op = float(L.get("opacity", 1.0))
        L_OP.append(op)

        bm = str(L.get("blend_mode","over")).lower().strip()
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
        if ui_mask_set:
            base = _layer_base_indices(tk_id, tref)
            inter = set(base) & set(ui_mask_set)
            # If intersection differs, synthesize a group for it and retarget layer to that group.
            if inter != base:
                gid = _ensure_group_for_set(inter)
                if gid >= 0:
                    tk_id = 1
                    tref = gid

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
            M_SRC.append(int(SRC.get(src,0)))
            tgt = str(m.get("target","brightness")).strip()
            M_TGT.append(int(tgt_map.get(tgt,0)))
            mm = str(m.get("mode","mul")).strip().lower()
            M_MODE.append(int(MODE.get(mm,0)))
            M_AMT.append(float(m.get("amount",0.0)))
            M_RATE.append(float(m.get("rate_hz",0.5)))
            M_BIAS.append(float(m.get("bias",0.0)))
            M_SMOOTH.append(float(m.get("smooth",0.0)))
            cv = str(m.get("curve","linear")).lower().strip()
            M_CURVE.append(int(CURVE.get(cv, 0)))
            M_PHASE.append(float(m.get("phase", 0.0)))

        # Operators: flatten up to OPS_PER_LAYER per layer
        ops_all = list(L.get("operators", []) or [])
        ops = []
        layer_effect_kind = str(L.get("effect") or L.get("behavior") or "").strip().lower()
        for oi, op in enumerate(ops_all):
            if not isinstance(op, dict):
                continue
            # Slot-0 may be a mirrored behavior entry (legacy LayerStack sync). Treat it as behavior, not PostFX.
            kind0 = str(op.get("kind") or op.get("op") or op.get("type") or "none").strip().lower()
            if oi == 0 and layer_effect_kind and kind0 == layer_effect_kind and kind0 not in OP_KIND_MAP:
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
            kid = OP_KIND_MAP.get(kind)
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

    sketch = """/ Generated by Modulo (Layer Stack)
// Export build: {EXPORT_MARKER}

// Debug option: print purpose channels over Serial
#define DBG_PURPOSE_SERIAL {1 if DBG_PURPOSE else 0}
#define DBG_SERIAL_BAUD {DBG_BAUD}

#include <math.h>

#define NUM_LEDS {num_leds}
#define LED_PIN {led_pin}

// LED backend implementation (filled by export target)
@@LED_IMPL@@

{postfx_decls}

#define LAYERS @@LAYER_COUNT@@

const uint8_t L_BEH[LAYERS]   = {{{_csv(L_BEH)}}};  // 0=solid,1=chase,2=wipe,3=sparkle,4=scanner,5=fade,6=strobe,7=rainbow,8=bouncer
const uint8_t L_R[LAYERS]     = {{{_csv(LR)}}};
const uint8_t L_G[LAYERS]     = {{{_csv(LG)}}};
const uint8_t L_B[LAYERS]     = {{{_csv(LB)}}};

const uint8_t L_R2[LAYERS]    = {{{_csv(L_R2)}}};
const uint8_t L_G2[LAYERS]    = {{{_csv(L_G2)}}};
const uint8_t L_B2[LAYERS]    = {{{_csv(L_B2)}}};

const float   L_DUTY[LAYERS]  = {{{_csv(L_DUTY)}}};
const uint8_t L_HUEOFF[LAYERS]= {{{_csv(L_HUEOFF)}}};
const float   L_HUESPAN[LAYERS]= {{{_csv(L_HUESPAN)}}};

const float   L_BR[LAYERS]    = {{{_csv(L_BR)}}};
	// Runtime overrides (Rules V6 can override a small deterministic subset)
	static float  L_BR_RT[LAYERS];
	static bool   L_BR_SET[LAYERS];
const float   L_SP[LAYERS]    = {{{_csv(L_SP)}}};
const float   L_WD[LAYERS]    = {{{_csv(L_WD)}}};
const float   L_SO[LAYERS]    = {{{_csv(L_SO)}}};
const float   L_DN[LAYERS]    = {{{_csv(L_DN)}}};
const float   L_DIR[LAYERS]   = {{{_csv(L_DIR)}}};

// Extra per-layer params (export defaults)
const float   L_PF0[LAYERS]   = {{{_csv(L_PF0)}}};
const float   L_PF1[LAYERS]   = {{{_csv(L_PF1)}}};
const float   L_PF2[LAYERS]   = {{{_csv(L_PF2)}}};
const float   L_PF3[LAYERS]   = {{{_csv(L_PF3)}}};
const int16_t L_PI0[LAYERS]   = {{{_csv(L_PI0)}}};
const int16_t L_PI1[LAYERS]   = {{{_csv(L_PI1)}}};
const int16_t L_PI2[LAYERS]   = {{{_csv(L_PI2)}}};
const int16_t L_PI3[LAYERS]   = {{{_csv(L_PI3)}}};

// Back-compat aliases for preview-only/game emitters
#define L_RBG L_R
#define L_GBG L_G
#define L_BBG L_B

// Purpose channels (signal bus; currently defaulted)
float purpose_f0 = 0.0f, purpose_f1 = 0.0f, purpose_f2 = 0.0f, purpose_f3 = 0.0f;
int16_t purpose_i0 = 0, purpose_i1 = 0, purpose_i2 = 0, purpose_i3 = 0;

{rules_decls}

// Modulotion runtime tables (defaults)
#ifndef MODS_PER_LAYER
#define MODS_PER_LAYER 4
#endif
#ifndef MODS_TOTAL
#define MODS_TOTAL (LAYERS * MODS_PER_LAYER)
#endif
float   M_PHASE[MODS_TOTAL] = {{0}};
uint8_t M_CURVE[MODS_TOTAL] = {{0}};

// Layer state tables for stateful effects (defaults)
#ifndef ST_F_SLOTS
#define ST_F_SLOTS 16
#endif
#ifndef ST_I_SLOTS
#define ST_I_SLOTS 16
#endif
uint8_t ST_INIT[LAYERS] = {{0}};
// C++ aggregate init: "{0}" zeros the whole table (including 2D arrays)
float   ST_F[LAYERS][ST_F_SLOTS] = {{0}};
int16_t ST_I[LAYERS][ST_I_SLOTS] = {{0}};
static inline void state_reset_layer(int li) {{
  ST_INIT[li] = 1;
  for (int k=0;k<ST_F_SLOTS;k++) ST_F[li][k] = 0.0f;
  for (int k=0;k<ST_I_SLOTS;k++) ST_I[li][k] = 0;
}}

const float   L_OP[LAYERS]    = {{{_csv(L_OP)}}};
// Runtime overrides (Rules V6 can override a small deterministic subset)
static float  L_OP_RT[LAYERS];
static bool   L_OP_SET[LAYERS];
const uint8_t L_BLEND[LAYERS] = {{{_csv(L_BLEND)}}}; // 0=over,1=add,2=max,3=multiply,4=screen
const uint8_t L_TGT_KIND[LAYERS] = {{{_csv(L_TK)}}};  // 0=all,1=group,2=zone
const int16_t L_TGT_REF[LAYERS]  = {{{_csv(L_TR)}}};

// Operators (per-layer, pre-blend). Deterministic subset:
// 0=none,1=gain,2=gamma,3=posterize
#define OPS_PER_LAYER {OPS_PER_LAYER}
const uint8_t OP_KIND[LAYERS*OPS_PER_LAYER] = {{{_csv(OP_KIND)}}};
const float   OP_P0[LAYERS*OPS_PER_LAYER]   = {{{_csv(OP_P0)}}};
// Runtime overrides (Rules V6 can override op_gain deterministically)
static float  OP_P0_RT[LAYERS*OPS_PER_LAYER];
static bool   OP_P0_SET[LAYERS*OPS_PER_LAYER];

// Modulotors (flattened: LAYERS*2 entries)
#define MODS_PER_LAYER {MODS_PER_LAYER}
const uint8_t M_SRC[LAYERS*MODS_PER_LAYER]  = {{{_csv(M_SRC)}}};   // 0 none, 1 lfo_sine, audio placeholders 10+
const uint8_t M_TGT[LAYERS*MODS_PER_LAYER]  = {{{_csv(M_TGT)}}};   // 0 br,1 sp,2 wd,3 so,4 dn,5 dir
const uint8_t M_MODE[LAYERS*MODS_PER_LAYER] = {{{_csv(M_MODE)}}};  // 0 mul,1 add,2 set
const float   M_AMT[LAYERS*MODS_PER_LAYER]  = {{{_csv(M_AMT)}}};
const float   M_RATE[LAYERS*MODS_PER_LAYER] = {{{_csv(M_RATE)}}};
const float   M_BIAS[LAYERS*MODS_PER_LAYER] = {{{_csv(M_BIAS)}}};
const float   M_SMOOTH[LAYERS*MODS_PER_LAYER]= {{{_csv(M_SMOOTH)}}};
float         M_LAST[LAYERS*MODS_PER_LAYER] = {{0}};

// Groups/Zones payload
const uint16_t GROUP_COUNT = {max(0, len(groups))};
const uint16_t ZONE_COUNT  = {max(0, len(zones))};
const uint16_t GROUP_OFFS[ (GROUP_COUNT>0)?GROUP_COUNT:1 ] = {{{_csv(group_offs if len(groups)>0 else [0])}}};
const uint16_t GROUP_LENS[ (GROUP_COUNT>0)?GROUP_COUNT:1 ] = {{{_csv(group_lens if len(groups)>0 else [0])}}};
const uint16_t GROUP_INDEXES[@@GROUP_INDEXES_LEN@@] = {{{_csv(group_indexes)}}};
const int16_t  ZONE_START[ (ZONE_COUNT>0)?ZONE_COUNT:1 ] = {{{_csv(zone_start if len(zones)>0 else [0])}}};
const int16_t  ZONE_END[   (ZONE_COUNT>0)?ZONE_COUNT:1 ] = {{{_csv(zone_end if len(zones)>0 else [0])}}};

static inline float clamp01(float x) {{
  if (x < 0.0f) return 0.0f;
  if (x > 1.0f) return 1.0f;
  return x;
}}

static inline float clamp255(float x) {{
  if (x < 0.0f) return 0.0f;
  if (x > 255.0f) return 255.0f;
  return x;
}}

// Operators runtime (per-layer, pre-blend)
static inline void apply_one_operator(uint8_t kind, float p0, float &r, float &g, float &b) {{
  if (kind == 1) {{ // gain
    float k = fmaxf(0.0f, p0);
    r = clamp255(r * k);
    g = clamp255(g * k);
    b = clamp255(b * k);
    return;
  }}
  if (kind == 2) {{ // gamma
    float gamma = fmaxf(0.001f, p0);
    float inv = 1.0f / gamma;
    r = powf(clamp01(r/255.0f), inv) * 255.0f;
    g = powf(clamp01(g/255.0f), inv) * 255.0f;
    b = powf(clamp01(b/255.0f), inv) * 255.0f;
    r = clamp255(r); g = clamp255(g); b = clamp255(b);
    return;
  }}
  if (kind == 3) {{ // posterize
    int levels = (int)roundf(p0);
    if (levels < 2) levels = 2;
    if (levels > 64) levels = 64;
    float step = 255.0f / (float)(levels - 1);
    r = clamp255(roundf(r / step) * step);
    g = clamp255(roundf(g / step) * step);
    b = clamp255(roundf(b / step) * step);
    return;
  }}
}}

static inline void apply_layer_operators(int li, float &r, float &g, float &b) {{
  int base = li * OPS_PER_LAYER;
  for (int oi=0; oi<OPS_PER_LAYER; oi++) {{
    uint8_t k = OP_KIND[base + oi];
    if (k == 0) continue;
    float p0 = OP_P0_RT[base + oi];
    apply_one_operator(k, p0, r, g, b);
  }}
}}

static inline float applyMode(float base, float sig, uint8_t mode, float amt) {{
  if (mode == 1) return base + sig * amt;       // add
  if (mode == 2) return sig * amt;             // set
  return base * (1.0f + sig * amt);            // mul
}}

static inline float blendChan(float outC, float layerC, uint8_t mode) {{
  if (mode == 1) {{ // add
    float v = outC + layerC;
    return (v > 255.0f) ? 255.0f : v;
  }}
  if (mode == 2) {{ // max
    return (outC > layerC) ? outC : layerC;
  }}
  if (mode == 3) {{ // multiply
    return (outC * layerC) / 255.0f;
  }}
  if (mode == 4) {{ // screen
    return 255.0f - ((255.0f - outC) * (255.0f - layerC)) / 255.0f;
  }}
  return layerC; // over
}}

static inline bool targetContains(uint16_t idx, uint8_t kind, int16_t ref) {{
  if (kind == 0) return true;
  if (kind == 2) {{
    if (ref < 0 || ref >= (int16_t)ZONE_COUNT) return true;
    int16_t a = ZONE_START[ref];
    int16_t b = ZONE_END[ref];
    if (a > b) {{ int16_t t=a; a=b; b=t; }}
    return (idx >= (uint16_t)a) && (idx <= (uint16_t)b);
  }}
  if (kind == 1) {{
    if (ref < 0 || ref >= (int16_t)GROUP_COUNT) return true;
    uint16_t off = GROUP_OFFS[ref];
    uint16_t len = GROUP_LENS[ref];
    for (uint16_t j=0; j<len; j++) {{
      if (GROUP_INDEXES[off + j] == idx) return true;
    }}
    return false;
  }}
  return true;
}}

// Simple RNG for sparkle (deterministic-ish)
static uint32_t rng_state = 0x12345678u;
static inline uint32_t xorshift32() {{
  uint32_t x = rng_state;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  rng_state = x;
  return x;
}}

static inline float lfo_sine(float t, float hz) {{
  return sinf(6.2831853f * hz * t);
}}

// Compute per-layer params with modulotors
static inline void computeLayerParams(int li, float t, float &br, float &sp, float &wd, float &so, float &dn, float &dir, float &pf0, float &pf1, float &pf2, float &pf3, float &pi0, float &pi1, float &pi2, float &pi3) {{
	  br = L_BR_RT[li]; sp = L_SP[li]; wd = L_WD[li]; so = L_SO[li]; dn = L_DN[li]; dir = L_DIR[li];
  pf0 = L_PF0[li]; pf1 = L_PF1[li]; pf2 = L_PF2[li]; pf3 = L_PF3[li];
  // ints normalized to 0..1 via soft range [-1000..1000]
  pi0 = clamp01(((float)L_PI0[li] + 1000.0f) / 2000.0f);
  pi1 = clamp01(((float)L_PI1[li] + 1000.0f) / 2000.0f);
  pi2 = clamp01(((float)L_PI2[li] + 1000.0f) / 2000.0f);
  pi3 = clamp01(((float)L_PI3[li] + 1000.0f) / 2000.0f);


  for (int mi=0; mi<MODS_PER_LAYER; mi++) {{
    int idx = li*MODS_PER_LAYER + mi;
    uint8_t src = M_SRC[idx];
    uint8_t tgt = M_TGT[idx];
    uint8_t mode = M_MODE[idx];
    float amt = M_AMT[idx];
    float rate = M_RATE[idx];
    float bias = M_BIAS[idx];
    float smooth = M_SMOOTH[idx];

    float sig = 0.0f;
    if (src == 0) {{ sig = 0.0f; }}
    else if (src == 1) {{ // lfo_sine
      sig = sinf(6.2831853f * (rate * t + M_PHASE[idx])); // [-1..1]
    }}
    else if (src == 10) {{ sig = (clamp01(g_energy) - 0.5f) * 2.0f; }}
    else if (src >= 11 && src <= 17) {{ sig = (clamp01(g_mono[src-11]) - 0.5f) * 2.0f; }}
    else if (src >= 21 && src <= 27) {{ sig = (clamp01((float)g_left[src-21] / 1023.0f) - 0.5f) * 2.0f; }}
    else if (src >= 31 && src <= 37) {{ sig = (clamp01((float)g_right[src-31] / 1023.0f) - 0.5f) * 2.0f; }}
    else if (src == 50) {{ sig = (clamp01(purpose_f0) - 0.5f) * 2.0f; }}
    else if (src == 51) {{ sig = (clamp01(purpose_f1) - 0.5f) * 2.0f; }}
    else if (src == 52) {{ sig = (clamp01(purpose_f2) - 0.5f) * 2.0f; }}
    else if (src == 53) {{ sig = (clamp01(purpose_f3) - 0.5f) * 2.0f; }}
    else if (src == 54) {{ sig = (clamp01((float)purpose_i0 * 0.001f) - 0.5f) * 2.0f; }}
    else if (src == 55) {{ sig = (clamp01((float)purpose_i1 * 0.001f) - 0.5f) * 2.0f; }}
    else if (src == 56) {{ sig = (clamp01((float)purpose_i2 * 0.001f) - 0.5f) * 2.0f; }}
    else if (src == 57) {{ sig = (clamp01((float)purpose_i3 * 0.001f) - 0.5f) * 2.0f; }}
    else {{ sig = 0.0f; }}


    // Convert to v in [0..1] for curve shaping, then back to [-1..1]
float v = 0.5f + 0.5f * sig;
uint8_t cv = M_CURVE[idx];
if (cv == 1) v = 1.0f - v;                 // invert
else if (cv == 2) v = fabsf((v - 0.5f) * 2.0f); // abs
else if (cv == 3) v = v * v;               // pow2
else if (cv == 4) v = v * v * v;           // pow3
sig = (v - 0.5f) * 2.0f; // back to [-1..1]

    if (smooth > 0.0f) {{
      float a = smooth;
      if (a < 0.0f) a = 0.0f;
      if (a > 0.999f) a = 0.999f;
      M_LAST[idx] = a * M_LAST[idx] + (1.0f - a) * sig;
      sig = M_LAST[idx];
    }}

    if (tgt == 0) br = clamp01(br + sig * amt + bias);
    else if (tgt == 1) sp = sp + sig * amt + bias;
    else if (tgt == 2) wd = clamp01(wd + sig * amt + bias);
    else if (tgt == 3) so = clamp01(so + sig * amt + bias);
    else if (tgt == 4) dn = clamp01(dn + sig * amt + bias);
    else if (tgt == 5) dir = applyMode(dir, sig, mode, amt);
  }}
}}

// Behavior evaluators: return layer RGB (0..255 floats) for LED i at time t.
static inline void evalSolid(int li, float br, float &r, float &g, float &b) {{
  r = (float)L_R[li] * br;
  g = (float)L_G[li] * br;
  b = (float)L_B[li] * br;
}}

static inline uint8_t clamp8(int v){{ if(v<0) return 0; if(v>255) return 255; return (uint8_t)v; }}

static inline void hsv2rgb(float h, float s, float v, float &r, float &g, float &b){{
  // h 0..1
  h = h - floorf(h);
  s = clamp01(s);
  v = clamp01(v);
  float hh = h * 6.0f;
  int i = (int)floorf(hh);
  float f = hh - (float)i;
  float p = v * (1.0f - s);
  float q = v * (1.0f - f*s);
  float t = v * (1.0f - (1.0f - f)*s);
  i = i % 6;
  if(i==0){{ r=v; g=t; b=p; }}
  else if(i==1){{ r=q; g=v; b=p; }}
  else if(i==2){{ r=p; g=v; b=t; }}
  else if(i==3){{ r=p; g=q; b=v; }}
  else if(i==4){{ r=t; g=p; b=v; }}
  else {{ r=v; g=p; b=q; }}
  r*=255.0f; g*=255.0f; b*=255.0f;
}}

static inline void evalFade(int li, float t, float br, float sp, float &r, float &g, float &b) {{
  float alpha = 0.5f * (1.0f + sinf(t * fmaxf(0.0f, sp) * 6.2831853f));
  float r1 = (float)L_R[li], g1=(float)L_G[li], b1=(float)L_B[li];
  float r2 = (float)L_R2[li], g2=(float)L_G2[li], b2=(float)L_B2[li];
  r = (r1 + (r2-r1)*alpha) * br;
  g = (g1 + (g2-g1)*alpha) * br;
  b = (b1 + (b2-b1)*alpha) * br;
}}

static inline void evalStrobe(int li, float t, float br, float sp, float duty, float &r, float &g, float &b) {{
  float hz = fmaxf(0.0f, sp);
  float d = clamp01(duty);
  bool on = true;
  if(hz > 0.0001f){{
    float phase = fmodf(t * hz, 1.0f);
    on = (phase < d);
  }}
  if(!on){{ r=0; g=0; b=0; return; }}
  r = (float)L_R[li] * br;
  g = (float)L_G[li] * br;
  b = (float)L_B[li] * br;
}}

static inline void evalRainbow(int li, int i, float t, float br, float sp, uint8_t off, float span, float &r, float &g, float &b) {{
  float base = ((float)off / 255.0f) + t * fmaxf(0.0f, sp) * 0.15f;
  float h = base + ((float)i / fmaxf(1.0f, (float)(NUM_LEDS-1))) * span;
  float rr, gg, bb;
  hsv2rgb(h, 1.0f, 1.0f, rr, gg, bb);
  r = rr * br;
  g = gg * br;
  b = bb * br;
}}

static inline void evalChase(int li, int i, float t, float br, float sp, float wd, float dir, float &r, float &g, float &b) {{
  float phase = fmodf(t * fmaxf(0.0f, sp), 1.0f);
  float pos01 = (dir >= 0.0f) ? phase : (1.0f - phase);
  float pos = pos01 * (float)(NUM_LEDS - 1);
  float halfw = fmaxf(0.5f, wd * (float)NUM_LEDS * 0.5f);
  float d = fabsf((float)i - pos);
  float a = (d <= halfw) ? (1.0f - (d/halfw)) : 0.0f;
  r = (float)L_R[li] * br * a;
  g = (float)L_G[li] * br * a;
  b = (float)L_B[li] * br * a;
}}


static inline uint8_t bit8(const uint8_t *rows, int x, int y){{
  if(x<0||y<0||x>7||y>7) return 0;
  uint8_t row = rows[y];
  return (row & (1 << (7-x))) ? 1 : 0;
}}

// Phase 2A: Tilemap+Sprite renderer (export path for tilemap_sprite / red_hat_runner / mariobros_clockface)
// Notes:
// - Uses pf0 as jump_now (Rules can set purpose_f0)
// - Uses speed for horizontal scroll
static inline void evalTilemapSprite(int li, int i, float t, float br, float sp, float pf0, float pf1, float &r, float &g, float &b){{
#ifndef MATRIX_WIDTH
  // Fallback for strip: simple moving dot
  float phase = fmodf(t * fmaxf(0.0f, sp), 1.0f);
  int pos = (int)floorf(phase * (float)(NUM_LEDS-1) + 0.5f);
  if(i==pos){{ r=(float)L_R[li]*br; g=(float)L_G[li]*br; b=(float)L_B[li]*br; }}
  else {{ r=0; g=0; b=0; }}
  return;
#else
  const int mw = (int)MATRIX_WIDTH;
  const int mh = (int)MATRIX_HEIGHT;
  int x = i % (mw>0?mw:1);
  int y = i / (mw>0?mw:1);

  // Variant id encoded in raw PI0 (set by exporter for tilemap/sprite showcase effects)
  const int variant = (int)L_PI0[li]; // 0=tilemap_sprite, 1=red_hat_runner, 2=mariobros_clockface

  // Default background: mario-ish sky + grass band + sprinkled bricks
  auto bg_default = [&](){{
    float skyR = 0.0f, skyG = 0.0f, skyB = 115.0f;
    float brickR = 230.0f, brickG = 89.0f, brickB = 16.0f;
    float grassR = 0.0f, grassG = 200.0f, grassB = 0.0f;

    bool is_grass = (y >= mh-8);
    bool is_brick = false;
    if(!is_grass){{
      if(y >= mh-24 && y < mh-16){{ if(((x/8) % 4) == 1) is_brick = true; }}
      if(y >= mh-40 && y < mh-32){{ if(((x/8) % 6) == 2) is_brick = true; }}
    }}

    if(is_grass){{ r = grassR * br; g = grassG * br; b = grassB * br; return; }}
    if(is_brick){{ r = brickR * br; g = brickG * br; b = brickB * br; return; }}
    r = skyR * br; g = skyG * br; b = skyB * br; return;
  }};

  // Variant 2: Mario clockface (deterministic millis-based clock)
  if(variant == 2){{
    bg_default();

    // Render mm:ss using a tiny 3x5 font, centered.
    int sec = (int)fmodf(t, 60.0f);
    int min = (int)fmodf(floorf(t/60.0f), 60.0f);
    int d0 = (min/10)%10, d1 = min%10, d2 = (sec/10)%10, d3 = sec%10;

    static const uint8_t DIG[10][5] = {{
      {{0b111,0b101,0b101,0b101,0b111}},
      {{0b010,0b110,0b010,0b010,0b111}},
      {{0b111,0b001,0b111,0b100,0b111}},
      {{0b111,0b001,0b111,0b001,0b111}},
      {{0b101,0b101,0b111,0b001,0b001}},
      {{0b111,0b100,0b111,0b001,0b111}},
      {{0b111,0b100,0b111,0b101,0b111}},
      {{0b111,0b001,0b010,0b010,0b010}},
      {{0b111,0b101,0b111,0b101,0b111}},
      {{0b111,0b101,0b111,0b001,0b111}},
    }};

    int sc = 1 + (int)floorf(clamp01(pf1) * 2.0f + 0.5f);
    if(sc<1) sc=1; if(sc>3) sc=3;

    int digitW = 3*sc;
    int digitH = 5*sc;
    int gap = 1*sc;
    int colonGap = 2*sc;
    int totalW = digitW*4 + gap*2 + colonGap;
    int x0 = (mw - totalW)/2;
    int y0 = 2;

    auto hit_digit = [&](int dx, int dy, int dig)->bool{{
      int rx = x - dx;
      int ry = y - dy;
      if(rx<0||ry<0||rx>=digitW||ry>=digitH) return false;
      int px = rx / sc;
      int py = ry / sc;
      uint8_t row = DIG[dig][py];
      bool on = ((row >> (2-px)) & 1) != 0;
      return on;
    }};

    bool hit = false;
    if(hit_digit(x0 + 0*(digitW+gap), y0, d0)) hit=true;
    if(hit_digit(x0 + 1*(digitW+gap), y0, d1)) hit=true;
    int colonX = x0 + 2*digitW + gap*2 + (colonGap/2);
    if(x>=colonX && x<colonX+sc){{
      if(y>=y0+1*sc && y<y0+2*sc) hit=true;
      if(y>=y0+3*sc && y<y0+4*sc) hit=true;
    }}
    int x2 = x0 + 2*digitW + gap*2 + colonGap;
    if(hit_digit(x2 + 0*(digitW+gap), y0, d2)) hit=true;
    if(hit_digit(x2 + 1*(digitW+gap), y0, d3)) hit=true;

    if(hit){{
      r = (float)L_R[li] * br;
      g = (float)L_G[li] * br;
      b = (float)L_B[li] * br;
    }}
    return;
  }}

  // Variant 1: Red Hat Runner
  if(variant == 1){{
    float skyR = 8.0f, skyG = 8.0f, skyB = 30.0f;
    float floorR = 70.0f, floorG = 70.0f, floorB = 70.0f;
    float pipeR = 10.0f, pipeG = 180.0f, pipeB = 40.0f;

    static const uint8_t SPRH[8] = {{
      0b00111100,
      0b01111110,
      0b11111111,
      0b01111110,
      0b00111100,
      0b00100100,
      0b01011010,
      0b10000001,
    }};

    float speed = fmaxf(0.0f, sp);
    int sx = (int)floorf(fmodf(t * speed * 12.0f, (float)(mw + 8)) - 8.0f);
    float jh = 4.0f + clamp01(pf1) * 14.0f;
    float jump = (pf0 > 0.5f) ? (fabsf(sinf(t * 6.2831853f)) * jh) : 0.0f;
    int sy = (mh - 14) - (int)floorf(jump + 0.5f);

    if(y >= mh-6){{ r = floorR * br; g = floorG * br; b = floorB * br; }}
    else {{ r = skyR * br; g = skyG * br; b = skyB * br; }}

    if(y >= mh-20 && y < mh-6){{
      int band = (int)fmodf(t*speed*2.0f, 8.0f);
      if(((x/8 + band) % 5) == 2){{ r = pipeR*br; g=pipeG*br; b=pipeB*br; }}
    }}

    if(x >= sx && x < sx+8 && y >= sy && y < sy+8){{
      if(bit8(SPRH, x-sx, y-sy)){{
        r = (float)L_R[li] * br;
        g = (float)L_G[li] * br;
        b = (float)L_B[li] * br;
        return;
      }}
    }}
    return;
  }}

  // Variant 0: generic tilemap_sprite
  static const uint8_t SPR[8] = {{
    0b00011000,
    0b00111100,
    0b01111110,
    0b00111100,
    0b00011000,
    0b00100100,
    0b01000010,
    0b10000001,
  }};

  float speed = fmaxf(0.0f, sp);
  int sx = (int)floorf(fmodf(t * speed * 10.0f, (float)(mw + 8)) - 8.0f);
  float jh = 4.0f + clamp01(pf1) * 12.0f;
  float jump = (pf0 > 0.5f) ? (fabsf(sinf(t * 6.2831853f)) * jh) : 0.0f;
  int sy = (mh - 16) - (int)floorf(jump + 0.5f);

  if(x >= sx && x < sx+8 && y >= sy && y < sy+8){{
    if(bit8(SPR, x-sx, y-sy)){{
      r = (float)L_R[li] * br;
      g = (float)L_G[li] * br;
      b = (float)L_B[li] * br;
      return;
    }}
  }}

  bg_default();
  return;
#endif
}}
// Phase 3B: CA cluster (Game of Life / Brian's Brain / Elementary CA / Langton's Ant)
// Export notes:
// - deterministic seed
// - updates at a fixed tick derived from speed
// - designed as stress-test proof path: runs on firmware with no external deps
static uint8_t CA_A[NUM_LEDS];
static uint8_t CA_B[NUM_LEDS];
static int CA_LAST_FRAME = -1;
static int CA_LAST_VARIANT = -1;
static uint8_t CA_INITED = 0;
static int ANT_X = 0, ANT_Y = 0, ANT_DIR = 0;

static inline void ca_init(int variant, float density01){
  CA_INITED = 1;
  CA_LAST_VARIANT = variant;
  CA_LAST_FRAME = -1;
  rng_state = 0xA5A5A5u ^ (uint32_t)(variant*2654435761u) ^ 0x1234567u;
#ifdef MATRIX_WIDTH
  int mw = (int)MATRIX_WIDTH;
  int mh = (int)MATRIX_HEIGHT;
  int n = mw*mh;
  if(n > NUM_LEDS) n = NUM_LEDS;
  float p = clamp01(density01);
  for(int i=0;i<n;i++){
    uint32_t rv = xorshift32();
    CA_A[i] = ((rv & 0xFFFFu) < (uint32_t)(p*65535.0f)) ? 1 : 0;
    CA_B[i] = 0;
  }
  // ant start
  ANT_X = mw/2; ANT_Y = mh/2; ANT_DIR = 0;
#else
  for(int i=0;i<NUM_LEDS;i++){ CA_A[i]=0; CA_B[i]=0; }
  CA_A[NUM_LEDS/2] = 1;
#endif
}

static inline void ca_step_elementary_rule30(){
  // 1D Rule 30 on CA_A -> CA_B (strip or top row), then swap.
  for(int i=0;i<NUM_LEDS;i++){
    uint8_t L = (i>0) ? CA_A[i-1] : 0;
    uint8_t C = CA_A[i];
    uint8_t R = (i<NUM_LEDS-1) ? CA_A[i+1] : 0;
    uint8_t pat = (L<<2)|(C<<1)|R;
    // Rule 30: 00011110 (bits 7..0), but we index by pat 0..7
    uint8_t out = (uint8_t)((0b00011110 >> pat) & 1);
    CA_B[i]=out;
  }
  for(int i=0;i<NUM_LEDS;i++) CA_A[i]=CA_B[i];
}

#ifdef MATRIX_WIDTH
static inline int ca_xy(int x,int y){ return XY(x,y); }

static inline void ca_step_life(){
  int mw = (int)MATRIX_WIDTH;
  int mh = (int)MATRIX_HEIGHT;
  for(int y=0;y<mh;y++){
    for(int x=0;x<mw;x++){
      int n=0;
      for(int dy=-1;dy<=1;dy++){
        int yy=y+dy; if(yy<0||yy>=mh) continue;
        for(int dx=-1;dx<=1;dx++){
          int xx=x+dx; if(xx<0||xx>=mw) continue;
          if(dx==0 && dy==0) continue;
          n += (CA_A[ca_xy(xx,yy)]?1:0);
        }
      }
      uint8_t cur = CA_A[ca_xy(x,y)];
      uint8_t nxt = 0;
      if(cur){
        nxt = (n==2 || n==3) ? 1 : 0;
      } else {
        nxt = (n==3) ? 1 : 0;
      }
      CA_B[ca_xy(x,y)] = nxt;
    }
  }
  int n = mw*mh; if(n>NUM_LEDS) n=NUM_LEDS;
  for(int i=0;i<n;i++) CA_A[i]=CA_B[i];
}

static inline void ca_step_brians_brain(){
  // States: 0=dead, 1=alive, 2=dying
  int mw = (int)MATRIX_WIDTH;
  int mh = (int)MATRIX_HEIGHT;
  for(int y=0;y<mh;y++){
    for(int x=0;x<mw;x++){
      int aliveN=0;
      for(int dy=-1;dy<=1;dy++){
        int yy=y+dy; if(yy<0||yy>=mh) continue;
        for(int dx=-1;dx<=1;dx++){
          int xx=x+dx; if(xx<0||xx>=mw) continue;
          if(dx==0 && dy==0) continue;
          aliveN += (CA_A[ca_xy(xx,yy)]==1)?1:0;
        }
      }
      uint8_t cur = CA_A[ca_xy(x,y)];
      uint8_t nxt = 0;
      if(cur==1) nxt=2;
      else if(cur==2) nxt=0;
      else { nxt = (aliveN==2) ? 1 : 0; }
      CA_B[ca_xy(x,y)] = nxt;
    }
  }
  int n = mw*mh; if(n>NUM_LEDS) n=NUM_LEDS;
  for(int i=0;i<n;i++) CA_A[i]=CA_B[i];
}

static inline void ca_step_langtons_ant(){
  int mw = (int)MATRIX_WIDTH;
  int mh = (int)MATRIX_HEIGHT;
  int idx = ca_xy(ANT_X, ANT_Y);
  uint8_t cell = CA_A[idx] & 1;
  if(cell==0){
    // turn right
    ANT_DIR = (ANT_DIR + 1) & 3;
    CA_A[idx] = 1;
  } else {
    // turn left
    ANT_DIR = (ANT_DIR + 3) & 3;
    CA_A[idx] = 0;
  }
  // move forward
  if(ANT_DIR==0) ANT_Y -= 1;
  else if(ANT_DIR==1) ANT_X += 1;
  else if(ANT_DIR==2) ANT_Y += 1;
  else ANT_X -= 1;

  if(ANT_X<0) ANT_X=0;
  if(ANT_Y<0) ANT_Y=0;
  if(ANT_X>=mw) ANT_X=mw-1;
  if(ANT_Y>=mh) ANT_Y=mh-1;
}
#endif

static inline void evalCACluster(int li, int i, float t, float br, float sp, float pf1, float &r, float &g, float &b){
  const int variant = (int)L_PI0[li]; // 0=brians,1=life,2=elementary,3=ant
  if(!CA_INITED || CA_LAST_VARIANT != variant){
    ca_init(variant, pf1);
  }
  // tick rate: 6..60 Hz derived from speed
  float hz = 6.0f + clamp01(sp) * 54.0f;
  int frame = (int)floorf(t * hz);
  if(frame != CA_LAST_FRAME){
    CA_LAST_FRAME = frame;
#ifdef MATRIX_WIDTH
    if(variant==0) ca_step_brians_brain();
    else if(variant==1) ca_step_life();
    else if(variant==3) ca_step_langtons_ant();
    else ca_step_life(); // default
#else
    ca_step_elementary_rule30();
#endif
  }

#ifdef MATRIX_WIDTH
  int mw=(int)MATRIX_WIDTH;
  int mh=(int)MATRIX_HEIGHT;
  int x = i % (mw>0?mw:1);
  int y = i / (mw>0?mw:1);
  int idx = XY(x,y);
  if(variant==0){
    uint8_t s = CA_A[idx];
    if(s==1){ r=255.0f*br; g=40.0f*br; b=10.0f*br; }
    else if(s==2){ r=20.0f*br; g=90.0f*br; b=255.0f*br; }
    else { r=0; g=0; b=0; }
    return;
  }
  if(variant==3){
    // ant highlighted
    if(x==ANT_X && y==ANT_Y){ r=255.0f*br; g=255.0f*br; b=255.0f*br; return; }
    uint8_t s = CA_A[idx] & 1;
    if(s){ r=20.0f*br; g=200.0f*br; b=40.0f*br; } else { r=0; g=0; b=0; }
    return;
  }
  // life
  uint8_t s = CA_A[idx] & 1;
  if(s){ r=(float)L_R[li]*br; g=(float)L_G[li]*br; b=(float)L_B[li]*br; }
  else { r=0; g=0; b=0; }
#else
  // strip elementary CA visualization
  uint8_t s = CA_A[i] & 1;
  if(s){ r=(float)L_R[li]*br; g=(float)L_G[li]*br; b=(float)L_B[li]*br; }
  else { r=0; g=0; b=0; }
#endif
}


static inline void evalMSGEQ7(int li, int i, float t, float br, float sp, float pf1, float &r, float &g, float &b){
  // pf1 = gain (default 1.0)
  float gain = pf1;
  if(gain < 0.05f) gain = 0.05f;
  if(gain > 4.0f) gain = 4.0f;

  const int variant = (int)L_PI0[li]; // 0=bars, 1=reactive strobe
  if(variant == 1){
    // Reactive strobe: energy drives duty
    float e = g_energy * gain;
    if(e < 0.0f) e = 0.0f;
    if(e > 1.0f) e = 1.0f;
    // Use time + energy to strobe
    float phase = fmodf(t * (6.0f + 40.0f*e), 1.0f);
    float on = (phase < (0.15f + 0.35f*e)) ? 1.0f : 0.0f;
    r = (float)L_R[li] * br * on;
    g = (float)L_G[li] * br * on;
    b = (float)L_B[li] * br * on;
    return;
  }

  // Bars: split canvas into 7 equal bands; fill each band based on mono[band]
  int n = NUM_LEDS;
  if(n < 7){ r=0; g=0; b=0; return; }
  int seg = n / 7;
  if(seg < 1) seg = 1;
  int band = i / seg;
  if(band < 0) band = 0;
  if(band > 6) band = 6;

  float v = g_mono[band] * gain; // 0..~1
  if(v < 0.0f) v = 0.0f;
  if(v > 1.0f) v = 1.0f;

  int within = i - band*seg;
  int filled = (int)(v * (float)seg);

  if(within < filled){
    r = (float)L_R[li] * br;
    g = (float)L_G[li] * br;
    b = (float)L_B[li] * br;
  }else{
    r=0; g=0; b=0;
  }
}


static inline void evalBouncer(int li, int i, float br, float sp, float wd, float &r, float &g, float &b) {{
  // Uses L_R/L_G/L_B as dot color and L_R2/L_G2/L_B2 as background.
  if (!ST_INIT[li]) state_reset_layer(li);
  float pos = ST_F[li][0];   // pos
  int center = (int)floorf(pos + 0.5f);
  int width = (int)floorf(wd + 0.5f);
  if (width < 1) width = 1;
  if (width > NUM_LEDS) width = NUM_LEDS;
  int half = width / 2;
  int start = center - half;
  int end = start + width;

  bool on = (i >= start && i < end);
  if (on) {{
    r = (float)L_R[li] * br;
    g = (float)L_G[li] * br;
    b = (float)L_B[li] * br;
  }} else {{
    r = (float)L_R2[li] * br;
    g = (float)L_G2[li] * br;
    b = (float)L_B2[li] * br;
  }}
}}

static inline void updateBouncer(int li, float dt, float sp) {{
  if (!ST_INIT[li]) state_reset_layer(li);
  float pos = ST_F[li][0];
  float vel = ST_F[li][1];
  if (vel == 0.0f) vel = 1.0f;

  float speed = sp;
  if (speed < 0.0f) {{
    vel = -fabsf(vel);
    speed = fabsf(speed);
  }} else {{
    vel = (vel >= 0.0f) ? fabsf(vel) : -fabsf(vel);
  }}

  pos += vel * speed * dt;

  if (pos < 0.0f) {{ pos = 0.0f; vel = fabsf(vel); }}
  if (pos > (float)(NUM_LEDS - 1)) {{ pos = (float)(NUM_LEDS - 1); vel = -fabsf(vel); }}

  ST_F[li][0] = pos;
  ST_F[li][1] = vel;
}}


static inline void resetBreakout(int li, float so, float dn) {{
  // blocks count 3..8 from density, hp 1..5 from softness
  int blocks = (int)roundf(3.0f + clamp01(dn) * 5.0f);
  if (blocks < 3) blocks = 3;
  if (blocks > 8) blocks = 8;
  int hp = (int)roundf(1.0f + clamp01(so) * 4.0f);
  if (hp < 1) hp = 1;
  if (hp > 5) hp = 5;
  // init block hp in ST_I[li][0..blocks-1], clear rest
  for (int k=0;k<8;k++) ST_I[li][k] = 0;
  for (int b=0;b<blocks;b++) ST_I[li][b] = hp;
  ST_I[li][6] = 0; // score
  ST_I[li][7] = 1; // lives placeholder
  // ball & paddle in ST_F
  ST_F[li][0] = (float)(NUM_LEDS - 5); // ball pos
  ST_F[li][1] = -1.0f;                // ball vel
  ST_F[li][2] = (float)(NUM_LEDS - 3); // paddle center
}}

static inline void updateBreakout(int li, float dt, float sp, float wd, float so, float dn, float pf0) {{
  if (!ST_INIT[li]) {{ state_reset_layer(li); resetBreakout(li, so, dn); ST_INIT[li]=1; }}
  int blocks = (int)roundf(3.0f + clamp01(dn) * 5.0f);
  if (blocks < 3) blocks = 3;
  if (blocks > 8) blocks = 8;
  int hp = (int)roundf(1.0f + clamp01(so) * 4.0f);
  if (hp < 1) hp = 1;
  if (hp > 5) hp = 5;

  int width = (int)wd;
  if (width < 2) width = 2;
  if (width > (NUM_LEDS/2)) width = NUM_LEDS/2;

  float ball = ST_F[li][0];
  float vel  = ST_F[li][1];
  float paddle = ST_F[li][2];

  if (vel == 0.0f) vel = -1.0f;
  float speed = fmaxf(0.0f, sp);
  // paddle control via purpose_f0 (0..1)
  if (pf0 > 0.02f) ST_F[li][2] = clamp01(pf0) * (float)(NUM_LEDS-1);
  // ship control 0..1 -> position
  ST_F[li][0] = clamp01(pf0) * (float)(NUM_LEDS-1);

  int blockRegion = max(6, NUM_LEDS/3);
  int blockW = max(1, blockRegion / blocks);

  // simple AI paddle follows ball
  float d = ball - paddle;
  if (d < -1.0f) d = -1.0f;
  if (d > 1.0f) d = 1.0f;
  paddle += d * speed * dt * 25.0f;
  float minP = (float)blockRegion + (float)width*0.5f;
  float maxP = (float)(NUM_LEDS-1) - (float)width*0.5f;
  if (paddle < minP) paddle = minP;
  if (paddle > maxP) paddle = maxP;

  // move ball
  ball += vel * speed * dt * 30.0f;

  if (ball < 0.0f) {{ ball = 0.0f; vel = fabsf(vel); }}
  if (ball > (float)(NUM_LEDS-1)) {{ ball = (float)(NUM_LEDS-1); vel = -fabsf(vel); }}

  // block collision
  if (ball < (float)blockRegion) {{
    int bi = (int)(ball / (float)blockW);
    if (bi >= 0 && bi < blocks && ST_I[li][bi] > 0) {{
      ST_I[li][bi] -= 1;
      ST_I[li][6] += 1; // score
      vel = fabsf(vel);
    }}
  }}

  // paddle collision
  if (vel > 0.0f) {{
    float pl = paddle - (float)width*0.5f;
    float pr = paddle + (float)width*0.5f;
    if (ball >= pl && ball <= pr) {{
      vel = -fabsf(vel);
      ball = pl - 0.1f;
    }}
  }}

  // win -> refill blocks
  bool any = false;
  for (int b=0;b<blocks;b++) if (ST_I[li][b] > 0) {{ any = true; break; }}
  if (!any) {{
    for (int b=0;b<blocks;b++) ST_I[li][b] = hp;
    vel = -fabsf(vel);
    ball = (float)(NUM_LEDS-5);
  }}

  ST_F[li][0] = ball;
  ST_F[li][1] = vel;
  ST_F[li][2] = paddle;
}}

static inline void evalBreakout(int li, int i, float br, float wd, float so, float dn, float &r, float &g, float &b) {{
  int blocks = (int)roundf(3.0f + clamp01(dn) * 5.0f);
  if (blocks < 3) blocks = 3;
  if (blocks > 8) blocks = 8;

  int width = (int)wd;
  if (width < 2) width = 2;
  if (width > (NUM_LEDS/2)) width = NUM_LEDS/2;

  int blockRegion = max(6, NUM_LEDS/3);
  int blockW = max(1, blockRegion / blocks);

  // default off
  r = g = b = 0.0f;

  // ball
  int ball = (int)roundf(ST_F[li][0]);
  if (i == ball) {{
    r = (float)L_R[li] * br;
    g = (float)L_G[li] * br;
    b = (float)L_B[li] * br;
    return;
  }}

  // blocks (use color2)
  if (i < blockRegion) {{
    int bi = i / blockW;
    if (bi >= 0 && bi < blocks && ST_I[li][bi] > 0) {{
      r = (float)L_R2[li] * br;
      g = (float)L_G2[li] * br;
      b = (float)L_B2[li] * br;
      return;
    }}
  }}

  // paddle (use bg color arrays in L_BG?? we store bg into L_RBG?? in exporter uses L_R2 for bg?)
  // In this exporter, bg is stored into L_R2/L_G2/L_B2 OR separate? We use L_R2 etc for secondary.
  // For breakout, we treat bg (paddle color) as L_R2/L_G2/L_B2 ONLY if you set color2; but we need distinct.
  // So we use L_R2/L_G2/L_B2 as blocks, and paddle uses L_RBG arrays if present; else fallback to blocks color.
  int hasBg = 0;
  #ifdef HAS_BG_COLOR
    hasBg = 1;
  #endif

  float paddle = ST_F[li][2];
  int pl = (int)roundf(paddle - (float)width*0.5f);
  int pr = (int)roundf(paddle + (float)width*0.5f);
  if (i >= pl && i <= pr) {{
    // paddle uses background color arrays if available, else uses blocks color2
    #if defined(L_RBG)
      r = (float)L_RBG[li] * br;
      g = (float)L_GBG[li] * br;
      b = (float)L_BBG[li] * br;
    #else
      r = (float)L_R2[li] * br;
      g = (float)L_G2[li] * br;
      b = (float)L_B2[li] * br;
    #endif
    return;
  }}
}}
static inline void resetAsteroids(int li, float so, float dn, float pi0) {{
  int k = (int)roundf(1.0f + clamp01(dn) * 2.0f);
  if (k < 1) k = 1;
  if (k > 3) k = 3;
  int hp = (int)roundf(1.0f + clamp01(so) * 4.0f);
  if (hp < 1) hp = 1;
  if (hp > 5) hp = 5;

  ST_F[li][0] = (float)(NUM_LEDS - 3); // ship
  ST_F[li][1] = 0.0f;                 // cooldown
  ST_F[li][2] = -1.0f; ST_F[li][3] = -1.0f; ST_F[li][4] = -1.0f; // bullets
  ST_F[li][5] = 2.0f; ST_F[li][6] = 5.0f; ST_F[li][7] = 8.0f;    // asteroid positions

  for (int i=0;i<8;i++) ST_I[li][i] = 0;
  for (int a=0;a<k;a++) ST_I[li][a] = hp; // asteroid hp
  ST_I[li][6] = 0; // score
}}

static inline void updateAsteroids(int li, float dt, float sp, float so, float dn, float pf0, float pf1, float pi0) {{
  if (!ST_INIT[li]) {{ state_reset_layer(li); resetAsteroids(li, so, dn, 0.0f); ST_INIT[li]=1; }}

  int k = (int)roundf(1.0f + clamp01(dn) * 2.0f);
  if (k < 1) k = 1;
  if (k > 3) k = 3;
  int hp0 = (int)roundf(1.0f + clamp01(so) * 4.0f);
  if (hp0 < 1) hp0 = 1;
  if (hp0 > 5) hp0 = 5;

  float speed = fmaxf(0.0f, sp);
  // paddle control via purpose_f0 (0..1)
  if (pf0 > 0.02f) ST_F[li][2] = clamp01(pf0) * (float)(NUM_LEDS-1);
  // ship control 0..1 -> position
  ST_F[li][0] = clamp01(pf0) * (float)(NUM_LEDS-1);

  // cooldown & auto-fire (purpose_f1 controls rate)
  float fireRate = 0.35f - clamp01(pf1) * 0.25f; // 0.35..0.10
  float cool = ST_F[li][1];
  cool -= dt;
  if (cool <= 0.0f) {{
    for (int b=0;b<3;b++) {{
      if (ST_F[li][2+b] < 0.0f) {{ ST_F[li][2+b] = ST_F[li][0] - 1.0f; break; }}
    }}
    cool = fireRate;
  }}
  ST_F[li][1] = cool;

  // move bullets left
  for (int b=0;b<3;b++) {{
    float bp = ST_F[li][2+b];
    if (bp >= 0.0f) {{
      bp -= speed * dt * 25.0f;
      if (bp < 0.0f) bp = -1.0f;
      ST_F[li][2+b] = bp;
    }}
  }}

  // move asteroids right slowly, wrap
  for (int a=0;a<k;a++) {{
    float ap = ST_F[li][5+a];
    ap += (2.0f + (float)a) * speed * dt * 3.0f;
    if (ap > (float)(NUM_LEDS-1)) ap = 0.0f;
    ST_F[li][5+a] = ap;
    if (ST_I[li][a] <= 0) {{ ST_I[li][a] = hp0; ST_F[li][5+a] = 0.0f; }}
  }}

  // collisions bullets vs asteroids
  for (int b=0;b<3;b++) {{
    float bp = ST_F[li][2+b];
    if (bp < 0.0f) continue;
    for (int a=0;a<k;a++) {{
      if (ST_I[li][a] <= 0) continue;
      float ap = ST_F[li][5+a];
      if (fabsf(ap - bp) <= 0.6f) {{
        ST_I[li][a] -= 1;
        ST_I[li][6] += 1;
        ST_F[li][2+b] = -1.0f;
        break;
      }}
    }}
  }}
}}

static inline void evalAsteroids(int li, int i, float br, float so, float dn, float &r, float &g, float &b) {{
  int k = (int)roundf(1.0f + clamp01(dn) * 2.0f);
  if (k < 1) k = 1;
  if (k > 3) k = 3;

  r = g = b = 0.0f;

  int ship = (int)roundf(ST_F[li][0]);
  if (i == ship) {{
    r = (float)L_RBG[li] * br;
    g = (float)L_GBG[li] * br;
    b = (float)L_BBG[li] * br;
    return;
  }}

  for (int bb=0; bb<3; bb++) {{
    int bp = (int)roundf(ST_F[li][2+bb]);
    if (bp >= 0 && i == bp) {{
      r = (float)L_R[li] * br;
      g = (float)L_G[li] * br;
      b = (float)L_B[li] * br;
      return;
    }}
  }}

  for (int a=0; a<k; a++) {{
    if (ST_I[li][a] <= 0) continue;
    int ap = (int)roundf(ST_F[li][5+a]);
    if (i == ap) {{
      r = (float)L_R2[li] * br;
      g = (float)L_G2[li] * br;
      b = (float)L_B2[li] * br;
      return;
    }}
  }}
}}

inline void evalWipe(int li, int i, float t, float br, float sp, float so, float dir, float &r, float &g, float &b) {{
  float phase = fmodf(t * fmaxf(0.0f, sp), 1.0f);
  float edge = ((dir >= 0.0f) ? phase : (1.0f - phase)) * (float)(NUM_LEDS - 1);
  float d = (float)i - edge;
  float a = 0.0f;
  if (so <= 0.001f) {{
    a = (d <= 0.0f) ? 1.0f : 0.0f;
  }} else {{
    float w = so * 10.0f; // softness in LEDs
    a = clamp01(1.0f - (d / fmaxf(0.001f, w)));
  }}
  r = (float)L_R[li] * br * a;
  g = (float)L_G[li] * br * a;
  b = (float)L_B[li] * br * a;
}}

// --- Phase 3E: Games cluster (Snake / Invaders / Shooter / Blocks+Ball) ---
// These are deterministic "lite" runtimes designed to be export-safe and board-agnostic.
// They operate in LED-index space (strip), which also renders on matrices via the mapping layer.

static inline void resetSnakeLite(int li) {
  state_reset_layer(li);
  ST_F[li][0] = 0.0f;   // head
  ST_F[li][1] = 1.0f;   // dir
  ST_F[li][2] = 6.0f;   // tail length
  ST_F[li][3] = 0.0f;   // accumulator
}

static inline void updateSnakeLite(int li, float dt, float sp, float pf0, float pf1, int pi0) {
  if (!ST_INIT[li]) { resetSnakeLite(li); ST_INIT[li]=1; }
  float speed = 2.0f + clamp01(sp) * 14.0f;     // steps per second
  float tail  = 3.0f + clamp01(pf1) * 24.0f;    // 3..27
  ST_F[li][2] = tail;

  // direction control: pi0 bit0 flips direction, pf0 can "nudge" (Rules V6)
  float dir = (pi0 & 1) ? -1.0f : 1.0f;
  if (pf0 > 0.75f) dir = -1.0f;
  else if (pf0 > 0.25f) dir = 1.0f;
  ST_F[li][1] = dir;

  ST_F[li][3] += dt * speed;
  while (ST_F[li][3] >= 1.0f) {
    ST_F[li][3] -= 1.0f;
    float h = ST_F[li][0] + dir;
    if (h < 0.0f) h = (float)(NUM_LEDS-1);
    if (h > (float)(NUM_LEDS-1)) h = 0.0f;
    ST_F[li][0] = h;
  }
}

static inline void evalSnakeLite(int li, int i, float br, float &r, float &g, float &b) {
  r=g=b=0.0f;
  int head = (int)roundf(ST_F[li][0]);
  int tail = (int)roundf(ST_F[li][2]);
  float dir = ST_F[li][1];
  if (i == head) { r = 0.0f; g = 255.0f * br; b = 60.0f * br; return; }
  // simple trailing glow behind head
  for (int k=1;k<=tail && k<=28;k++){
    int idx = head - (int)(dir * (float)k);
    while (idx < 0) idx += NUM_LEDS;
    while (idx >= NUM_LEDS) idx -= NUM_LEDS;
    if (i == idx) {
      float a = 1.0f - ((float)k / (float)(tail+1));
      r = 20.0f * br * a;
      g = 200.0f * br * a;
      b = 40.0f * br * a;
      return;
    }
  }
}

static inline void resetInvadersLite(int li) {
  state_reset_layer(li);
  ST_F[li][0] = 0.0f;  // phase
  ST_F[li][1] = 1.0f;  // dir
  ST_F[li][2] = 0.0f;  // accumulator
}

static inline void updateInvadersLite(int li, float dt, float sp, float pf0, float pf1, int pi0) {
  if (!ST_INIT[li]) { resetInvadersLite(li); ST_INIT[li]=1; }
  float speed = 0.25f + clamp01(sp) * 2.0f; // scroll speed
  ST_F[li][0] += dt * speed * ((pi0 & 1) ? -1.0f : 1.0f);
  if (ST_F[li][0] < 0.0f) ST_F[li][0] += 1.0f;
  if (ST_F[li][0] > 1.0f) ST_F[li][0] -= 1.0f;
}

static inline void evalInvadersLite(int li, int i, float br, float &r, float &g, float &b) {
  r=g=b=0.0f;
  // repeating invader columns
  int period = 14;
  int off = (int)floorf(ST_F[li][0] * (float)period);
  int p = (i + off) % period;
  if (p == 2 || p == 3 || p == 10 || p == 11) {
    r = 255.0f * br;
    g = 40.0f * br;
    b = 20.0f * br;
  } else if (p == 6 || p == 7) {
    r = 50.0f * br;
    g = 220.0f * br;
    b = 50.0f * br;
  }
}

static inline void resetShooterLite(int li) {
  state_reset_layer(li);
  ST_F[li][0] = (float)(NUM_LEDS/2); // ship
  ST_F[li][1] = -1.0f;              // bullet
  ST_F[li][2] = 0.0f;               // fire phase
  ST_F[li][3] = 0.0f;               // accumulator
}

static inline void updateShooterLite(int li, float dt, float sp, float pf0, float pf1, int pi0) {
  if (!ST_INIT[li]) { resetShooterLite(li); ST_INIT[li]=1; }
  float speed = 0.8f + clamp01(sp) * 3.0f;

  // ship drift (deterministic)
  ST_F[li][0] += dt * speed * 6.0f * ((pi0 & 1) ? -1.0f : 1.0f);
  if (ST_F[li][0] < 1.0f) ST_F[li][0] = (float)(NUM_LEDS-2);
  if (ST_F[li][0] > (float)(NUM_LEDS-2)) ST_F[li][0] = 1.0f;

  // fire trigger via pf0 > 0.5 OR periodic
  ST_F[li][2] += dt * (0.6f + clamp01(pf1) * 2.0f);
  bool want_fire = (pf0 > 0.5f) || (ST_F[li][2] >= 1.0f);
  if (ST_F[li][2] >= 1.0f) ST_F[li][2] -= 1.0f;

  if (want_fire && ST_F[li][1] < 0.0f) {
    ST_F[li][1] = ST_F[li][0]; // spawn bullet at ship
  }

  // bullet move
  if (ST_F[li][1] >= 0.0f) {
    ST_F[li][1] += dt * (12.0f + clamp01(sp) * 20.0f);
    if (ST_F[li][1] > (float)(NUM_LEDS-1)) ST_F[li][1] = -1.0f;
  }
}

static inline void evalShooterLite(int li, int i, float br, float &r, float &g, float &b) {
  r=g=b=0.0f;
  int ship = (int)roundf(ST_F[li][0]);
  int bull = (int)roundf(ST_F[li][1]);
  if (i == ship) { r = 30.0f * br; g = 120.0f * br; b = 255.0f * br; return; }
  if (ST_F[li][1] >= 0.0f && i == bull) { r = 255.0f * br; g = 255.0f * br; b = 255.0f * br; return; }
  // enemies: periodic red dots
  if ((i % 17) == 0) { r = 255.0f * br; g = 30.0f * br; b = 20.0f * br; }
}

static inline void resetBlocksBallLite(int li) {
  state_reset_layer(li);
  ST_F[li][0] = (float)(NUM_LEDS - 4); // ball
  ST_F[li][1] = -1.0f;                // vel
  ST_F[li][2] = (float)(NUM_LEDS - 6); // paddle
  ST_I[li][0] = 12;                   // blocks count
}

static inline void updateBlocksBallLite(int li, float dt, float sp, float pf0, float pf1, int pi0) {
  if (!ST_INIT[li]) { resetBlocksBallLite(li); ST_INIT[li]=1; }
  float speed = 6.0f + clamp01(sp) * 18.0f;
  float ball = ST_F[li][0];
  float vel  = (ST_F[li][1] == 0.0f) ? -1.0f : ST_F[li][1];

  // paddle control via pf0
  if (pf0 > 0.02f) ST_F[li][2] = clamp01(pf0) * (float)(NUM_LEDS - 1);

  ball += vel * dt * speed;
  if (ball < 0.0f) { ball = 0.0f; vel = -vel; }
  if (ball > (float)(NUM_LEDS-1)) { ball = (float)(NUM_LEDS-1); vel = -vel; }

  // simple "block hit" region at start of strip
  int blocks = ST_I[li][0];
  int bi = (int)roundf(ball);
  if (blocks > 0 && bi < blocks) {
    ST_I[li][0] = blocks - 1;
    vel = -vel;
  }

  ST_F[li][0] = ball;
  ST_F[li][1] = vel;
}

static inline void evalBlocksBallLite(int li, int i, float br, float &r, float &g, float &b) {
  r=g=b=0.0f;
  int blocks = ST_I[li][0];
  if (i < blocks) { r = 200.0f * br; g = 80.0f * br; b = 20.0f * br; return; }
  int ball = (int)roundf(ST_F[li][0]);
  if (i == ball) { r = 255.0f * br; g = 255.0f * br; b = 120.0f * br; return; }
  int paddle = (int)roundf(ST_F[li][2]);
  if (abs(i - paddle) <= 1) { r = 30.0f * br; g = 255.0f * br; b = 120.0f * br; return; }
}


static inline void evalSparkle(int li, int i, float t, float br, float dn, float &r, float &g, float &b) {{
  // dn is density 0..1; sparkle chance per frame per led
  // use hashed RNG based on led and time bucket
  uint32_t bucket = (uint32_t)(t * 30.0f); // 30fps-ish bucket
  uint32_t h = (uint32_t)i * 2654435761u ^ bucket * 2246822519u ^ 0x9E3779B9u;
  h ^= h >> 16; h *= 2246822519u; h ^= h >> 13; h *= 3266489917u; h ^= h >> 16;
  float u = (float)(h & 0xFFFFu) / 65535.0f;
  float a = (u < dn) ? 1.0f : 0.0f;
  r = (float)L_R[li] * br * a;
  g = (float)L_G[li] * br * a;
  b = (float)L_B[li] * br * a;
}}

static inline float smoothstep(float x) {{
  x = clamp01(x);
  return x*x*(3.0f - 2.0f*x);
}}

static inline void evalScanner(int li, int i, float t, float br, float sp, float wd, float so, float dir, float &r, float &g, float &b) {{
  float phase = fmodf(t * fmaxf(0.2f, sp), 1.0f);
  float tri = 1.0f - fabsf(2.0f*phase - 1.0f);
  float pos01 = (dir >= 0.0f) ? tri : (1.0f - tri);
  float pos = pos01 * (float)(NUM_LEDS - 1);
  float halfw = fmaxf(0.5f, wd * (float)NUM_LEDS * 0.5f);
  float d = fabsf((float)i - pos);
  float a = 0.0f;
  if (d <= halfw) {{
    if (so <= 0.001f) a = 1.0f;
    else {{
      float x = 1.0f - (d / halfw);
      a = (1.0f - so) * 1.0f + so * smoothstep(x);
    }}
  }}
  r = (float)L_R[li] * br * a;
  g = (float)L_G[li] * br * a;
  b = (float)L_B[li] * br * a;
}}

static uint32_t __last_ms = 0;
static float    __accum_s = 0.0f;
static const float __FIXED_DT = 1.0f/60.0f;

static uint8_t LAST_BEH[LAYERS];

void setup() {{
  if (DBG_PURPOSE_SERIAL) {{
    Serial.begin(DBG_SERIAL_BAUD);
    delay(10);
  }}

  modulo_led_init();
  msgeq7_setup();
  modulo_wifi_init();
}}

void loop() {{
  unsigned long now = millis();
  modulo_wifi_tick();
  float t = (float)now / 1000.0f;
  msgeq7_read();

  // Reset per-frame rule-driven runtime overrides
#if MODULA_POSTFX_ENABLED
  PFX_TRAIL_RT = PFX_TRAIL_BASE; PFX_TRAIL_SET = false;
  PFX_BLEED_RT = PFX_BLEED_BASE; PFX_BLEED_SET = false;
  PFX_BLEED_R_RT = PFX_BLEED_R_BASE; PFX_BLEED_R_SET = false;
#endif
  for (int li=0; li<LAYERS; li++) {{
    L_OP_RT[li] = L_OP[li]; L_OP_SET[li] = false;
    L_BR_RT[li] = L_BR[li]; L_BR_SET[li] = false;
    // Operator param runtime overrides (Rules V6: op_gain)
    for (int oi=0; oi<OPS_PER_LAYER; oi++) {{
      int idx = li * OPS_PER_LAYER + oi;
      OP_P0_RT[idx] = OP_P0[idx];
      OP_P0_SET[idx] = false;
    }}
  }}

{rules_apply}

  for (int i=0; i<NUM_LEDS; i++) {{
    float outR = 0.0f, outG = 0.0f, outB = 0.0f;

    for (int li=0; li<LAYERS; li++) {{
      if (!targetContains((uint16_t)i, L_TGT_KIND[li], L_TGT_REF[li])) continue;

      float br, sp, wd, so, dn, dir;
      float pf0=0.0f, pf1=0.0f, pf2=0.0f, pf3=0.0f;
      float pi0=0.0f, pi1=0.0f, pi2=0.0f, pi3=0.0f;
      computeLayerParams(li, t, br, sp, wd, so, dn, dir, pf0, pf1, pf2, pf3, pi0, pi1, pi2, pi3);

      float lr=0.0f, lg=0.0f, lb=0.0f;
      uint8_t beh = L_BEH[li];
      if (beh == 0) evalSolid(li, br, lr, lg, lb);
      else if (beh == 8) evalBouncer(li, i, br, sp, wd, lr, lg, lb);
      else if (beh == 5) evalFade(li, t, br, sp, lr, lg, lb);
      else if (beh == 6) evalStrobe(li, t, br, sp, L_DUTY[li], lr, lg, lb);
      else if (beh == 7) evalRainbow(li, i, t, br, sp, L_HUEOFF[li], L_HUESPAN[li], lr, lg, lb);
      else if (beh == 11) evalTilemapSprite(li, i, t, br, sp, pf0, pf1, lr, lg, lb);
      else if (beh == 12) evalCACluster(li, i, t, br, sp, pf1, lr, lg, lb);
      else if (beh == 13) evalMSGEQ7(li, i, t, br, sp, pf1, lr, lg, lb);
      else if (beh == 9) evalBreakout(li, i, br, wd, so, dn, lr, lg, lb);
      else if (beh == 10) evalAsteroids(li, i, br, so, dn, lr, lg, lb);
      else if (beh == 14) evalSnakeLite(li, i, br, lr, lg, lb);
      else if (beh == 15) evalInvadersLite(li, i, br, lr, lg, lb);
      else if (beh == 16) evalShooterLite(li, i, br, lr, lg, lb);
      else if (beh == 17) evalBlocksBallLite(li, i, br, lr, lg, lb);
      else if (beh == 1) evalChase(li, i, t, br, sp, wd, dir, lr, lg, lb);
      else if (beh == 2) evalWipe(li, i, t, br, sp, so, dir, lr, lg, lb);
      else if (beh == 3) evalSparkle(li, i, t, br, dn, lr, lg, lb);
      else if (beh == 4) evalScanner(li, i, t, br, sp, wd, so, dir, lr, lg, lb);
      else evalSolid(li, br, lr, lg, lb);

      // Apply per-layer operators before blend/opacity
      apply_layer_operators(li, lr, lg, lb);

      float op = clamp01(L_OP_RT[li]);

      float blendedR = blendChan(outR, lr, L_BLEND[li]);
      float blendedG = blendChan(outG, lg, L_BLEND[li]);
      float blendedB = blendChan(outB, lb, L_BLEND[li]);

      outR = outR * (1.0f - op) + blendedR * op;
      outG = outG * (1.0f - op) + blendedG * op;
      outB = outB * (1.0f - op) + blendedB * op;
    }}

    leds[i] = CRGB((uint8_t)clamp01(outR/255.0f)*255, (uint8_t)clamp01(outG/255.0f)*255, (uint8_t)clamp01(outB/255.0f)*255);
  }}

{postfx_apply}
  modulo_led_show();
}}

"""
    sketch = sketch.replace("{1 if DBG_PURPOSE else 0}", str(1 if DBG_PURPOSE else 0))
    sketch = sketch.replace("{DBG_BAUD}", str(DBG_BAUD))
    sketch = sketch.replace("{num_leds}", str(num_leds))
    sketch = sketch.replace("{int(num_leds)}", str(int(num_leds)))
    sketch = sketch.replace("{int(led_pin)}", str(int(led_pin)))
    return sketch


def export_project_layerstack(*, project: dict, template_path, out_path, replacements: dict | None = None):
    code = make_layerstack_sketch(project=project)
    rep = dict(replacements or {})

    # derived counts for token replacements
    layers_list = list((project or {}).get('layers') or [])
    rep.setdefault('LAYER_COUNT', str(len(layers_list)))
    if 'GROUP_INDEXES_LEN' not in rep:
        gi = rep.get('GROUP_INDEXES')
        if isinstance(gi, str):
            s = gi.strip()
            if s.startswith('{') and s.endswith('}'):
                inner = s[1:-1].strip()
                if not inner:
                    rep['GROUP_INDEXES_LEN'] = '0'
                else:
                    rep['GROUP_INDEXES_LEN'] = str(len([p for p in inner.split(',') if p.strip()]))
        if 'GROUP_INDEXES_LEN' not in rep:
            rep['GROUP_INDEXES_LEN'] = '0'

    # Ensure LED backend is always defined; targets may override this token.
    rep.setdefault("LED_IMPL", FASTLED_LED_IMPL)

    # Matrix implementation
    rep.setdefault("MATRIX_IMPL", "")
    try:
        layout = project.get("layout") or {}
        kind = str(layout.get("kind") or layout.get("shape") or "").strip().lower()
        if kind in ("matrix","cells"):
            rep["MATRIX_IMPL"] = MATRIX_IMPL
    except Exception:
        rep["MATRIX_IMPL"] = ""
    return export_sketch(sketch_code=code, template_path=template_path, out_path=out_path, replacements=rep)



def validate_project_layout_compat(project: dict) -> None:
    """Fail export if any layer uses an effect whose `supports` doesn't match the current layout."""
    try:
        layout_kind = (project.get("layout") or {}).get("kind")
    except Exception:
        layout_kind = None

    if layout_kind not in ("strip","cells"):
        return

    from behaviors.registry import load_capabilities_catalog
    caps = load_capabilities_catalog().get("effects", {}) or {}
    bad = []
    layers = project.get("layers") or []
    for i, layer in enumerate(layers):
        try:
            key = (layer.get("effect") or "").strip()
        except Exception:
            key = ""
        if not key:
            continue
        c = caps.get(key) or {}
        supports = str(c.get("supports","both"))
        if layout_kind == "strip" and supports not in ("strip","both"):
            bad.append((i, key, supports))
        if layout_kind == "cells" and supports not in ("cells","both"):
            bad.append((i, key, supports))

    if bad:
        msg = "Layout incompatibility: project is %s but these layers are not supported:\n" % layout_kind
        for i, key, supports in bad[:20]:
            msg += f"  layer[{i}] effect='{key}' supports={supports}\n"
        if len(bad) > 20:
            msg += f"  ...and {len(bad)-20} more\n"
        msg += "Fix: change layout OR remove/replace those layers."
        raise ExportValidationError(msg)

def export_project_validated(project: dict, out_path: Path, *, template_path: Path | None = None, replacements: dict | None = None) -> Path:
    """Validated export entrypoint used by UI."""
    res = _check_preconditions(project or {})
    if isinstance(res, tuple) and len(res) == 3:
        ok, problems, _warns = res
    else:
        ok, problems = res
    if not ok:
        msg = "Export preconditions failed:\n"
        for p in (problems or []):
            msg += f"- {p}\n"
        raise ExportValidationError(msg.strip())
    validate_project_layout_compat(project)

    # Early block: if any behavior in the project is not exportable, stop now with the most
    # meaningful reason. This avoids confusing secondary blockers (e.g. rules surface checks)
    # when the project cannot export anyway due to preview-only behaviors.
    try:
        for li, layer in enumerate((project or {}).get('layers') or []):
            if not isinstance(layer, dict):
                continue
            beh = str(layer.get('behavior') or layer.get('effect') or '').strip()
            if not beh:
                continue
            elig = get_eligibility(beh)
            if getattr(elig, 'status', '') != ExportStatus.EXPORTABLE:
                reason = getattr(elig, 'reason', '') or 'Not exportable'
                raise ExportValidationError(f"[E_BEHAVIOR_NOT_EXPORTABLE] layer {li} behavior '{beh}' is {elig.status}: {reason}")
    except ExportValidationError:
        raise
    except Exception:
        # Never hard-fail export due to eligibility probe; continue into deeper validation.
        pass

    # Matrix exports: derive export.hw.matrix from layout when absent (cells-first workflow).
    # This keeps export deterministic without forcing the user to manually add export.hw.matrix.
    layout0 = (project or {}).get("layout") or {}
    if str(layout0.get("kind") or "").strip().lower() in ("matrix","cells"):
        exp0 = (project or {}).get("export") or {}
        if not isinstance(exp0, dict):
            exp0 = {}
            project["export"] = exp0
        hw0 = exp0.get("hw") or exp0.get("hardware")
        if not isinstance(hw0, dict):
            hw0 = {}
            exp0["hw"] = hw0
        m0 = hw0.get("matrix")
        if not (isinstance(m0, dict) and (m0.get("width") is not None) and (m0.get("height") is not None)):
            mw = int(layout0.get("width") or 0)
            mh = int(layout0.get("height") or 0)
            if mw > 0 and mh > 0:
                hw0["matrix"] = {
                    "width": mw,
                    "height": mh,
                    "origin": str(layout0.get("origin") or "top_left"),
                    "serpentine": bool(layout0.get("serpentine") or False),
                    "rotate": int(layout0.get("rotate") or 0),
                    "flip_x": bool(layout0.get("flip_x") or False),
                    "flip_y": bool(layout0.get("flip_y") or False),
                }


    tpl = template_path or (Path(__file__).resolve().parents[1] / "export" / "arduino_template.ino.tpl")

    # Provide safe defaults for tokens if the target pack didn't supply replacements.
    # Target packs may override any of these.
    if replacements is None:
        replacements = {}

    # LED implementation block is required by the generated sketch; default to FastLED.
    replacements.setdefault("LED_IMPL", FASTLED_LED_IMPL)
    # WiFi/OTA defaults (targets may override via replacements)
    replacements.setdefault('WIFI_ENABLE', '0')
    replacements.setdefault('WIFI_SSID', '')
    replacements.setdefault('WIFI_PASSWORD', '')
    replacements.setdefault('WIFI_HOSTNAME', 'modulo')
    replacements.setdefault('WIFI_NTP_ENABLE', '1')
    replacements.setdefault('WIFI_TZ', 'GMT0BST,M3.5.0/1,M10.5.0/2')
    replacements.setdefault('WIFI_NTP1', 'pool.ntp.org')
    replacements.setdefault('WIFI_NTP2', 'time.nist.gov')

    # Audio backend selection: prefer explicit export.audio_backend when present; fall back to legacy ui.export_target.
    ui = (project or {}).get('ui') or {}
    exp = (project or {}).get('export') or {}
    explicit_ab = str(exp.get('audio_backend') or '').strip().lower()
    if explicit_ab == 'none':
        replacements.setdefault('USE_MSGEQ7', '0')
    elif explicit_ab == 'msgeq7':
        replacements.setdefault('USE_MSGEQ7', '1')
    else:
        # Legacy UI defaulting
        ui = (project or {}).get('ui') or {}
        export_target = str(ui.get('export_target') or '').strip().lower()
        if export_target in ('basic', 'no_audio'):
            replacements.setdefault('USE_MSGEQ7', '0')
        elif export_target in ('msgeq7', 'msgeq7_stereo', 'audio_msgeq7'):
            replacements.setdefault('USE_MSGEQ7', '1')
        else:
            # Back-compat: keep legacy default (enabled)
            replacements.setdefault('USE_MSGEQ7', '1')

        # MSGEQ7 wiring defaults: templates contain these tokens even when audio is disabled.
    # Target packs / UI may override via replacements.
    replacements.setdefault('MSGEQ7_RESET_PIN', '5')
    replacements.setdefault('MSGEQ7_STROBE_PIN', '4')
    replacements.setdefault('MSGEQ7_LEFT_PIN', 'A0')
    replacements.setdefault('MSGEQ7_RIGHT_PIN', 'A1')

# Wiring defaults (UI may override these; otherwise fall back to project layout)
    layout = (project or {}).get('layout') or {}

    # Matrix defaults: ensure required matrix tokens are present when layout.kind == 'matrix'.
    try:
        if str(layout.get('kind') or '').strip().lower() in ('matrix','cells'):
            exp0 = (project or {}).get('export') or {}
            hw0 = exp0.get('hw') or exp0.get('hardware') or {}
            mcfg = hw0.get('matrix') if isinstance(hw0, dict) else None
            if isinstance(mcfg, dict):
                mw = int(mcfg.get('width') or 0)
                mh = int(mcfg.get('height') or 0)
                serp = mcfg.get('serpentine')
                origin = str(mcfg.get('origin') or 'top_left').strip()
            else:
                mw = int(layout.get('width') or 0)
                mh = int(layout.get('height') or 0)
                serp = layout.get('serpentine')
                origin = str(layout.get('origin') or 'top_left').strip()
            if mw > 0 and mh > 0:
                replacements.setdefault('MATRIX_WIDTH', str(mw))
                replacements.setdefault('MATRIX_HEIGHT', str(mh))
                # For matrix layouts, LED count is derived from width*height
                layout['led_count'] = int(mw) * int(mh)
                layout['num_leds'] = layout['led_count']
            if serp is None:
                serp = False
            replacements.setdefault('MATRIX_SERPENTINE', '1' if bool(serp) else '0')
            replacements.setdefault('MATRIX_ORIGIN', origin.lower())
            # Optional matrix orientation helpers
            rot = 0
            try:
                rot = int((mcfg.get('rotate') if isinstance(mcfg, dict) else layout.get('rotate')) or 0)
            except Exception:
                rot = 0
            if rot not in (0, 90, 180, 270):
                rot = 0
            fx = 0
            fy = 0
            try:
                fx = 1 if bool((mcfg.get('flip_x') if isinstance(mcfg, dict) else layout.get('flip_x')) or False) else 0
                fy = 1 if bool((mcfg.get('flip_y') if isinstance(mcfg, dict) else layout.get('flip_y')) or False) else 0
            except Exception:
                fx = 0
                fy = 0
            replacements.setdefault('MATRIX_ROTATE', str(rot))
            replacements.setdefault('MATRIX_FLIP_X', str(fx))
            replacements.setdefault('MATRIX_FLIP_Y', str(fy))
    except Exception:
        pass
    # Data pin: allow numeric or board-specific pin tokens.
    # Prefer export.hw.data_pin when present (): layerstack sketch must reflect the resolved hardware pin.
    exp = (project or {}).get('export') or {}
    hw = exp.get('hw') or exp.get('hardware') or {}
    if isinstance(hw, dict) and hw.get('data_pin') is not None and str(hw.get('data_pin')).strip() != '':
        try:
            layout['led_pin'] = int(hw.get('data_pin'))
        except Exception:
            layout['led_pin'] = hw.get('data_pin')
    # If the caller provided a DATA_PIN replacement (target defaults / resolved config), keep layerstack sketch consistent.
    try:
        if isinstance(replacements, dict) and str(replacements.get('DATA_PIN') or '').strip():
            layout['led_pin'] = int(str(replacements.get('DATA_PIN')).strip())
    except Exception:
        pass
    data_pin = str(ui.get('export_data_pin') or '').strip() or str(layout.get('led_pin', 6))
    replacements.setdefault("DATA_PIN", data_pin)

    replacements.setdefault("LED_TYPE", str(ui.get('export_led_type') or '').strip() or "WS2812B")
    replacements.setdefault("COLOR_ORDER", str(ui.get('export_color_order') or '').strip() or "GRB")
    # Brightness: clamp to 0..255
    b = ui.get('export_brightness', '')
    if b is None or str(b).strip() == "":
        exp = (project or {}).get('export') or {}
        hw = exp.get('hw') or exp.get('hardware') or {}
        if isinstance(hw, dict) and hw.get('brightness') is not None:
            b = hw.get('brightness')
    try:
        bv = int(float(str(b).strip()))
    except Exception:
        bv = 255
    if bv < 0:
        bv = 0
    if bv > 255:
        bv = 255
    replacements.setdefault("LED_BRIGHTNESS", str(bv))

    return export_project_layerstack(project=project, template_path=tpl, out_path=out_path, replacements=replacements)



def export_project(*, project: dict, out_path: Path, template_path: Path | None = None):
    """Compatibility wrapper for multi-target exporters ().

    Returns (written_path, report_text).
    """
    p = export_project_validated(project, out_path, template_path=template_path)
    report = f"Target: arduino_avr_fastled_msgeq7\nWritten: {p}\n"
    return Path(p), report


MATRIX_IMPL = r"""

// Matrix layout
#define MATRIX_WIDTH @@MATRIX_WIDTH@@
#define MATRIX_HEIGHT @@MATRIX_HEIGHT@@
#define MATRIX_SERPENTINE @@MATRIX_SERPENTINE@@
#define MATRIX_ORIGIN "@@MATRIX_ORIGIN@@"
#define MATRIX_ROTATE @@MATRIX_ROTATE@@  // 0, 90, 180, 270
#define MATRIX_FLIP_X @@MATRIX_FLIP_X@@  // 0/1
#define MATRIX_FLIP_Y @@MATRIX_FLIP_Y@@  // 0/1

// Helper: use mapped indices when writing LEDs
#define MODULA_LED(i) leds[modulo_map_index((uint16_t)(i))]

// Map (x,y) -> linear index, applying origin + serpentine.
static inline uint16_t modulo_xy(uint16_t x, uint16_t y) {

  // origin transform
  if (strcmp(MATRIX_ORIGIN, "top_right") == 0 || strcmp(MATRIX_ORIGIN, "TR") == 0) {
    x = (MATRIX_WIDTH - 1) - x;
  } else if (strcmp(MATRIX_ORIGIN, "bottom_left") == 0 || strcmp(MATRIX_ORIGIN, "BL") == 0) {
    y = (MATRIX_HEIGHT - 1) - y;
  } else if (strcmp(MATRIX_ORIGIN, "bottom_right") == 0 || strcmp(MATRIX_ORIGIN, "BR") == 0) {
    x = (MATRIX_WIDTH - 1) - x;
    y = (MATRIX_HEIGHT - 1) - y;
  } else {
    // top_left (default)
  }

// Optional: rotate/flip logical coordinates before serpentine/origin mapping.
// NOTE: For 90/270, best results when MATRIX_WIDTH==MATRIX_HEIGHT or when the project dimensions
// already reflect the rotated physical orientation. Values are clamped for safety.
#if (MATRIX_ROTATE == 90)
  { uint16_t _tx = x; x = (uint16_t)((MATRIX_HEIGHT - 1) - y); y = _tx; }
#elif (MATRIX_ROTATE == 180)
  x = (uint16_t)((MATRIX_WIDTH - 1) - x);
  y = (uint16_t)((MATRIX_HEIGHT - 1) - y);
#elif (MATRIX_ROTATE == 270)
  { uint16_t _tx = x; x = y; y = (uint16_t)((MATRIX_WIDTH - 1) - _tx); }
#else
  // 0
#endif

#if MATRIX_FLIP_X
  x = (uint16_t)((MATRIX_WIDTH - 1) - x);
#endif
#if MATRIX_FLIP_Y
  y = (uint16_t)((MATRIX_HEIGHT - 1) - y);
#endif

  if (x >= MATRIX_WIDTH) x = MATRIX_WIDTH - 1;
  if (y >= MATRIX_HEIGHT) y = MATRIX_HEIGHT - 1;

  uint16_t row = y;
  if (MATRIX_SERPENTINE && (row & 1)) {
    return (row * MATRIX_WIDTH) + (MATRIX_WIDTH - 1 - x);
  } else {
    return (row * MATRIX_WIDTH) + x;
  }
}

// Map logical linear index -> physical linear index.
static inline uint16_t modulo_map_index(uint16_t i) {
  uint16_t n = (uint16_t)(MATRIX_WIDTH * MATRIX_HEIGHT);
  if (i >= n) return i;
  uint16_t x = (uint16_t)(i % MATRIX_WIDTH);
  uint16_t y = (uint16_t)(i / MATRIX_WIDTH);
  return modulo_xy(x, y);
}


"""


# Back-compat alias for target packs expecting NEOPIXELBUS_LED_IMPL
NEOPIXELBUS_LED_IMPL = NEOPIXELBUS_LED_IMPL_ESP32