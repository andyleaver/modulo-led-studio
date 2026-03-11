from __future__ import annotations

from runtime.resolver import resolve_project_postfx

from export.arduino_exporter_block_common import TOKEN_RE, EXPORT_MARKER

def _emit_postfx_blocks(*, project: dict, surface_kind: str, num_leds: int) -> tuple[str, str]:
    """Phase 7F: Arduino PostFX blocks (decls + apply code), memory-safe limits.

    Supports:
      - strip: bleed radius=1 (3-tap blur mix) + trail blend
      - cells/matrix: bleed radius=1 (self + 4-neighbors) using XY(x,y) mapping + trail blend

    Auto-disables for large LED counts on memory-limited boards.
    """
    pf, _pf_src = resolve_project_postfx(project=project, runtime=None)
    bleed_amount = float(pf.get("bleed_amount", 0.0) or 0.0)
    bleed_radius = int(pf.get("bleed_radius", 1) or 1)
    trail_amount = float(pf.get("trail_amount", 0.0) or 0.0)

    shape_s = str(surface_kind).lower().strip()
    if shape_s not in ("strip", "cells"):
        return ("// PostFX disabled (unsupported layout)\\n", "// PostFX disabled\\n")

    # Enable PostFX emission if base config uses it OR Rules can override it at runtime.
    uses_trail_override = False
    uses_bleed_override = False
    try:
        for r in (project or {}).get("rules") or []:
            if not isinstance(r, dict) or not bool(r.get("enabled", True)):
                continue
            act = r.get("action") if isinstance(r.get("action"), dict) else {}
            if str(act.get("kind", "") or "") != "set_layer_param":
                continue
            _pp = str(act.get("param", "") or "").strip().lower()
            if _pp == "project.postfx.trail_amount":
                uses_trail_override = True
            elif _pp in ("project.postfx.bleed_amount", "project.postfx.bleed_radius"):
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
    decls.append("  // Runtime overrides (Rules)")
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
        if kind_s == "strip":
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
    # Uses PFX_TRAIL_RT so Rules can override trail at runtime.
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

__all__ = ["TOKEN_RE", "EXPORT_MARKER", "_emit_postfx_blocks"]
