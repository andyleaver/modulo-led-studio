from __future__ import annotations


class PreviewEngineBlendMixin:
    @staticmethod
    def _u8(value: float) -> int:
        try:
            return int(max(0, min(255, float(value))))
        except Exception:
            return 0

    def _blend_over(self, dst, src, opacity: float):
        op = max(0.0, min(1.0, float(opacity or 0.0)))
        if op <= 0.0:
            return list(dst)
        out = []
        for i in range(min(len(dst), len(src))):
            dr, dg, db = dst[i]
            sr, sg, sb = src[i]
            out.append((
                self._u8(dr * (1.0 - op) + sr * op),
                self._u8(dg * (1.0 - op) + sg * op),
                self._u8(db * (1.0 - op) + sb * op),
            ))
        return out

    def _blend_add(self, dst, src, opacity: float):
        op = max(0.0, min(1.0, float(opacity or 0.0)))
        if op <= 0.0:
            return list(dst)
        out = []
        for i in range(min(len(dst), len(src))):
            dr, dg, db = dst[i]
            sr, sg, sb = src[i]
            out.append((
                self._u8(dr + (sr * op)),
                self._u8(dg + (sg * op)),
                self._u8(db + (sb * op)),
            ))
        return out

    def _blend_max(self, dst, src, opacity: float):
        op = max(0.0, min(1.0, float(opacity or 0.0)))
        if op <= 0.0:
            return list(dst)
        out = []
        for i in range(min(len(dst), len(src))):
            dr, dg, db = dst[i]
            sr, sg, sb = src[i]
            out.append((
                max(int(dr), self._u8(sr * op)),
                max(int(dg), self._u8(sg * op)),
                max(int(db), self._u8(sb * op)),
            ))
        return out

    def _blend_multiply(self, dst, src, opacity: float):
        op = max(0.0, min(1.0, float(opacity or 0.0)))
        if op <= 0.0:
            return list(dst)
        out = []
        for i in range(min(len(dst), len(src))):
            dr, dg, db = dst[i]
            sr, sg, sb = src[i]
            mr = dr * (sr / 255.0)
            mg = dg * (sg / 255.0)
            mb = db * (sb / 255.0)
            out.append((
                self._u8((dr * (1.0 - op)) + (mr * op)),
                self._u8((dg * (1.0 - op)) + (mg * op)),
                self._u8((db * (1.0 - op)) + (mb * op)),
            ))
        return out

    def _blend_screen(self, dst, src, opacity: float):
        op = max(0.0, min(1.0, float(opacity or 0.0)))
        if op <= 0.0:
            return list(dst)
        out = []
        for i in range(min(len(dst), len(src))):
            dr, dg, db = dst[i]
            sr, sg, sb = src[i]
            rr = 255.0 - ((255.0 - dr) * (255.0 - sr) / 255.0)
            rg = 255.0 - ((255.0 - dg) * (255.0 - sg) / 255.0)
            rb = 255.0 - ((255.0 - db) * (255.0 - sb) / 255.0)
            out.append((
                self._u8((dr * (1.0 - op)) + (rr * op)),
                self._u8((dg * (1.0 - op)) + (rg * op)),
                self._u8((db * (1.0 - op)) + (rb * op)),
            ))
        return out

    def _blend(self, dst, src, blend_mode: str, opacity: float):
        bm = str(blend_mode or 'over').strip().lower()
        if bm == 'add':
            return self._blend_add(dst, src, opacity)
        if bm == 'max':
            return self._blend_max(dst, src, opacity)
        if bm == 'multiply':
            return self._blend_multiply(dst, src, opacity)
        if bm == 'screen':
            return self._blend_screen(dst, src, opacity)
        return self._blend_over(dst, src, opacity)

    def _apply_layer_operators(self, layer, effect_id: str, frame):
        if not isinstance(frame, list) or not frame:
            return list(frame or [])
        from preview.preview_engine_support import _pe_get
        ops_all = list(_pe_get(layer, 'operators', []) or [])
        if not ops_all:
            return list(frame)
        layer_effect_kind = str(effect_id or _pe_get(layer, 'behavior', '') or '').strip().lower()
        overrides = _pe_get(layer, '_op_overrides', {}) or {}
        if not isinstance(overrides, dict):
            overrides = {}

        known_ops = {'gain', 'gamma', 'posterize'}
        ops = []
        for oi, op in enumerate(ops_all):
            if not isinstance(op, dict):
                continue
            kind = str(op.get('kind') or op.get('op') or op.get('type') or 'none').strip().lower()
            if oi == 0 and layer_effect_kind and kind == layer_effect_kind and kind not in known_ops:
                continue
            if bool(op.get('enabled', True)) is False:
                continue
            ops.append(op)

        out = list(frame)
        for op in ops:
            params_op = op.get('params') if isinstance(op.get('params'), dict) else {}
            kind = str(op.get('kind') or op.get('op') or op.get('type') or 'none').strip().lower()
            if kind == 'gain':
                try:
                    gain = float(overrides.get('gain', op.get('gain', params_op.get('gain', op.get('p0', 1.0)))))
                except Exception:
                    gain = 1.0
                out = [(self._u8(r * gain), self._u8(g * gain), self._u8(b * gain)) for (r, g, b) in out]
            elif kind == 'gamma':
                try:
                    gamma = float(overrides.get('gamma', op.get('gamma', params_op.get('gamma', op.get('p0', 2.2)))))
                except Exception:
                    gamma = 2.2
                if gamma > 0.0 and gamma != 1.0:
                    inv = 1.0 / gamma
                    out = [
                        (
                            self._u8(255.0 * ((max(0.0, min(255.0, float(r))) / 255.0) ** inv)),
                            self._u8(255.0 * ((max(0.0, min(255.0, float(g))) / 255.0) ** inv)),
                            self._u8(255.0 * ((max(0.0, min(255.0, float(b))) / 255.0) ** inv)),
                        )
                        for (r, g, b) in out
                    ]
            elif kind == 'posterize':
                try:
                    levels = float(overrides.get('posterize_levels', op.get('levels', op.get('steps', params_op.get('posterize_levels', op.get('p0', 8))))))
                except Exception:
                    levels = 8.0
                steps = max(2, int(levels))
                denom = max(1, steps - 1)
                out = [
                    (
                        self._u8(round((r / 255.0) * denom) * (255.0 / denom)),
                        self._u8(round((g / 255.0) * denom) * (255.0 / denom)),
                        self._u8(round((b / 255.0) * denom) * (255.0 / denom)),
                    )
                    for (r, g, b) in out
                ]
        return out
