from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple, Any
from app.masks_resolver import resolve_mask_to_indices

import traceback

import behaviors  # noqa: F401
from behaviors.registry import REGISTRY
import copy
from preview import postfx
from behaviors.state import EffectState
from preview.sim_clock import SimClock
from params.ensure import ensure_params
from params.resolve import resolve
from params.registry import PARAMS
from params.resolve import _clamp_param as _clamp_param

RGB = Tuple[int, int, int]


import inspect
from behaviors.state import EffectContext

def _call_preview_emit(beh, *, num_leds: int, params: dict, t: float, state: dict, layout: dict, dt: float, audio: dict):
    """Call behavior preview_emit with flexible signature support."""
    fn = getattr(beh, 'preview_emit', None)
    if fn is None:
        return [(0, 0, 0)] * int(num_leds)
    ctx = EffectContext(layout=dict(layout or {}), dt=float(dt), t=float(t), audio=dict(audio or {}))
    out_buf = [(0, 0, 0)] * int(num_leds)
    # --- effect compatibility shim -------------------------------------------------
    # A number of effects were ported from older prototypes and expect
    # pre-derived values inside params. We supply them here so preview and
    # effect-audit are deterministic even when the user hasn't configured an
    # audio backend.
    if isinstance(params, dict):
        _p = params
        try:
            if '_mw' not in _p or '_mh' not in _p:
                _p = dict(_p)
                _p.setdefault('_mw', int((layout or {}).get('mw') or 0))
                _p.setdefault('_mh', int((layout or {}).get('mh') or 0))
        except Exception:
            pass

        # Always refresh audio-derived dicts every frame (they drive particle
        # spawns and transient detection).
        try:
            a = audio if isinstance(audio, dict) else {}
            mono = list(a.get('mono') or [0.0]*7)
            l = list(a.get('L') or a.get('l') or [0.0]*7)
            r = list(a.get('R') or a.get('r') or [0.0]*7)
            if len(mono) < 7: mono = (mono + [0.0]*7)[:7]
            if len(l) < 7: l = (l + [0.0]*7)[:7]
            if len(r) < 7: r = (r + [0.0]*7)[:7]
            energy = float(a.get('energy', 0.0) or 0.0)

            af = {'energy': energy}
            for i in range(7):
                af[f'mono{i}'] = float(mono[i])
                af[f'l{i}'] = float(l[i])
                af[f'r{i}'] = float(r[i])

            if _p is params:
                _p = dict(_p)
            _p['_audio_flat'] = af

            # lightweight tempo estimate (legacy callers just need something stable)
            if '_audio_tempo' not in _p:
                _p['_audio_tempo'] = {'bpm': 120.0}

            # Transients are derived from per-band deltas. Store previous levels
            # on params so the effect sees consistent edges.
            prev = _p.get('_audio_prev')
            if not isinstance(prev, dict):
                prev = {}
            ev = {}
            # aggregate
            ev['energy'] = energy
            ev['energy_l'] = sum(af[f'l{i}'] for i in range(7)) / 7.0
            ev['energy_r'] = sum(af[f'r{i}'] for i in range(7)) / 7.0

            # per-band levels + transients
            for i in range(7):
                lv = af[f'l{i}']; rv = af[f'r{i}']
                mv = af[f'mono{i}']
                ev[f'l{i}_level'] = lv
                ev[f'r{i}_level'] = rv
                ev[f'mono{i}_level'] = mv
                # delta-based transient
                pl = float(prev.get(f'l{i}', lv))
                pr = float(prev.get(f'r{i}', rv))
                pm = float(prev.get(f'mono{i}', mv))
                ev[f'l{i}_tr'] = max(0.0, lv - pl)
                ev[f'r{i}_tr'] = max(0.0, rv - pr)
                ev[f'mono{i}_tr'] = max(0.0, mv - pm)
                prev[f'l{i}'] = lv
                prev[f'r{i}'] = rv
                prev[f'mono{i}'] = mv

            _p['_audio_prev'] = prev
            _p['_audio_events'] = ev

            # Purpose defaults (used by purpose_* effects): map to mono bands.
            for i in range(7):
                _p.setdefault(f'purpose_f{i}', af[f'mono{i}'])
            _p.setdefault('purpose_energy', energy)

        except Exception:
            # Never let shims break rendering.
            pass

        # If we created a shimmed copy, use it for the effect call.
        params = _p

    # -----------------------------------------------------------------------

    try:
        sig = inspect.signature(fn)
        want = sig.parameters
    except Exception:
        want = {}
    candidates = {
        'num_leds': int(num_leds),
        'n': int(num_leds),
        'count': int(num_leds),
        'params': params,
        't': float(t),
        'time': float(t),
        'dt': float(dt),
        'state': state,
        'ctx': ctx,
        'context': ctx,
        'layout': dict(layout or {}),
        'audio': dict(audio or {}),
        'out': out_buf,
        'buf': out_buf,
        'pixels': out_buf,
        'leds': out_buf,
    }
    if want:
        kw = {k: v for k, v in candidates.items() if k in want}
        has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in want.values())
        if has_varkw:
            for k in ('num_leds','params','t','dt','state','ctx','layout','audio'):
                kw.setdefault(k, candidates[k])
    else:
        kw = {'num_leds': int(num_leds), 'params': params, 't': float(t)}
    res = fn(**kw)
    # Effects may either return a frame list, or mutate the provided out buffer and return None.
    if res is None:
        return out_buf
    # Accept list/tuple of RGB
    try:
        if isinstance(res, (list, tuple)):
            rr = list(res)
            if len(rr) == int(num_leds):
                return [(int(r)&255, int(g)&255, int(b)&255) for (r,g,b) in rr]
    except Exception:
        pass
    # Fallback
    return out_buf


def _apply_project_param_rules(project, layers, audio_dict, t: float):
    """Project-level Rules MVP (Phase 2.2).

    Rules are editor-authored and stored at project.rules as a list of dicts.
    They apply *runtime overrides* to layer params (do not mutate saved params).

    MVP supports numeric (float) params only.

    Rule dict (tolerant):
      enabled: bool
      src_kind: 'param'|'audio' (default 'param')
      src_layer: int (if src_kind == param)
      src_param: str (if src_kind == param)
      src_audio: str (if src_kind == audio; e.g. 'energy', 'mono0', 'l2', 'r6')
      cond: 'gt'|'lt'|'between'
      a: float (threshold / low)
      b: float (high for between)
      dst_layer: int
      dst_param: str
      action: 'set'|'add'
      value: float
    """
    try:
        rules = getattr(project, 'rules', [])
    except Exception:
        rules = []
    if not isinstance(rules, list) or not rules:
        return [{} for _ in (layers or [])]

    overrides = [{} for _ in (layers or [])]
    for r in rules:
        if not isinstance(r, dict):
            continue
        try:
            if not bool(r.get('enabled', True)):
                continue
        except Exception:
            pass
        src_kind = str(r.get('src_kind', 'param') or 'param').strip().lower()
        try:
            dl = int(r.get('dst_layer', -1))
        except Exception:
            continue
        if dl < 0 or dl >= len(layers):
            continue

        # Destination param must always be present.
        dp = str(r.get('dst_param', '') or '').strip()
        if not dp:
            continue

        # Source selection depends on kind.
        if src_kind in ('audio', 'a'):
            sl = -1
            sp = ''
        else:
            try:
                sl = int(r.get('src_layer', -1))
            except Exception:
                continue
            if sl < 0 or sl >= len(layers):
                continue
            sp = str(r.get('src_param', '') or '').strip()
            if not sp:
                continue
        sv = None
        if src_kind in ('audio', 'a'):
            ak = str(r.get('src_audio', 'energy') or 'energy').strip().lower()
            try:
                sv = float((audio_dict or {}).get(ak, 0.0) or 0.0)
            except Exception:
                sv = None
        else:
            # Source value: base param + any prior override on that layer
            try:
                src_base = dict(getattr(layers[sl], 'params', {}) or {})
            except Exception:
                src_base = {}
            if sp in overrides[sl]:
                src_base[sp] = overrides[sl][sp]
            try:
                sv = float(src_base.get(sp, 0.0) or 0.0)
            except Exception:
                sv = None
        if sv is None:
            continue

        cond = str(r.get('cond', 'gt') or 'gt').lower().strip()
        try:
            a = float(r.get('a', r.get('thr', 0.5)) or 0.5)
        except Exception:
            a = 0.5
        try:
            b = float(r.get('b', 1.0) or 1.0)
        except Exception:
            b = 1.0
        ok = False
        if cond in ('lt', '<'):
            ok = sv < a
        elif cond in ('between', 'rng', 'range'):
            lo = min(a, b); hi = max(a, b)
            ok = (lo <= sv <= hi)
        else:
            ok = sv > a
        if not ok:
            continue

        action = str(r.get('action', 'set') or 'set').lower().strip()
        try:
            val = float(r.get('value', 0.0) or 0.0)
        except Exception:
            val = 0.0

        # Destination base: saved param + any prior override
        try:
            dst_base = dict(getattr(layers[dl], 'params', {}) or {})
        except Exception:
            dst_base = {}
        if dp in overrides[dl]:
            dst_base[dp] = overrides[dl][dp]
        try:
            cur = float(dst_base.get(dp, 0.0) or 0.0)
        except Exception:
            cur = 0.0
        outv = (cur + val) if action in ('add', 'inc', '+') else val
        outv = _clamp_param(dp, outv)
        overrides[dl][dp] = outv

    return overrides

def _normalize_modulotors(mods):
    """Normalize modulotors into runtime objects with a .sample(...) method.

    The project schema stores modulotors as dicts (and older builds may store
    ModulotorSpec dataclasses). Preview needs runtime objects that implement
    .sample(t, audio=...).

    This function is intentionally tolerant: unknown/bad specs are ignored.
    """
    import types
    from params.modulotors import Modulotor as _M, sample as _sample

    out = []
    for m in (mods or []):
        if m is None:
            continue
        # Already runtime
        if hasattr(m, "sample") and callable(getattr(m, "sample")):
            # If it has an "enabled" flag, respect it.
            try:
                if hasattr(m, "enabled") and not bool(getattr(m, "enabled")):
                    continue
            except Exception:
                pass
            out.append(m)
            continue

        # Dict spec (preferred)
        if isinstance(m, dict):
            try:
                if not bool(m.get("enabled", True)):
                    continue
                mm = _M(
                    source=str(m.get("source", "none")),
                    target=str(m.get("target", "brightness")),
                    mode=str(m.get("mode", "mul")),
                    amount=float(m.get("amount", 0.5) or 0.5),
                    rate_hz=float(m.get("rate_hz", m.get("freq", 0.5)) or 0.5),
                    bias=float(m.get("bias", 0.0) or 0.0),
                    smooth=float(m.get("smooth", 0.0) or 0.0),
                )
                mm.sample = types.MethodType(_sample, mm)
                out.append(mm)
            except Exception:
                continue
            continue

        # Dataclass-ish spec (ModulotorSpec)
        try:
            enabled = bool(getattr(m, "enabled", True))
        except Exception:
            enabled = True
        if not enabled:
            continue
        try:
            mm = _M(
                source=str(getattr(m, "source", "none")),
                target=str(getattr(m, "target", "brightness")),
                mode=str(getattr(m, "mode", "mul")),
                amount=float(getattr(m, "amount", 0.5) or 0.5),
                rate_hz=float(getattr(m, "rate_hz", getattr(m, "freq", 0.5)) or 0.5),
                bias=float(getattr(m, "bias", 0.0) or 0.0),
                smooth=float(getattr(m, "smooth", 0.0) or 0.0),
            )
            mm.sample = types.MethodType(_sample, mm)
            out.append(mm)
        except Exception:
            continue
            try:
                if float(self._showcase_flash_until) > 0.0 and float(t) < float(self._showcase_flash_until):
                    out = [(0, 0, 255)] * len(out)
            except Exception:
                pass

    return out

def _blend_chan(base: float, layer: float, mode: str) -> float:
    mode = (mode or "over").lower().strip()
    if mode in ("add", "plus"):
        return min(255.0, base + layer)
    if mode in ("sub", "subtract"):
        return max(0.0, base - layer)
    if mode in ("mul", "multiply"):
        return (base * layer) / 255.0
    if mode in ("screen",):
        return 255.0 - ((255.0 - base) * (255.0 - layer) / 255.0)
    return layer


def _apply_event_var_routes(project, layers, all_states):
    """Apply project-level event->var routing table ().

    Schema (tolerant): project.data['routes'] or project.routes
    route dict fields:
      - src_layer (int), event_key (str)
      - dst_layer (int), var (str)
      - op: set/inc/dec (default inc)
      - factor (float, default 1.0)
      - clamp_min/clamp_max optional
      - only_if_event_gt (int, default 0)
    """
    try:
        data = getattr(project, 'data', None)
        if isinstance(project, dict):
            data = project
        if data is None and hasattr(project, '__dict__'):
            data = project.__dict__
    except Exception:
        data = {}
    routes = None
    try:
        routes = (data or {}).get('routes')
    except Exception:
        routes = None
    if routes is None:
        try:
            routes = getattr(project, 'routes', None)
        except Exception:
            routes = None
    if not isinstance(routes, list) or not routes:
        return
    for r in routes:
        if not isinstance(r, dict):
            continue
        try:
            if not bool(r.get('enabled', True)):
                continue
        except Exception:
            pass
        try:
            sL = int(r.get('src_layer', r.get('src', -1)) or -1)
            dL = int(r.get('dst_layer', r.get('dst', -1)) or -1)
        except Exception:
            continue
        if sL < 0 or dL < 0:
            continue
        if sL >= len(all_states) or dL >= len(all_states):
            continue
        src_state = all_states[sL]
        dst_state = all_states[dL]
        if not isinstance(src_state, dict) or not isinstance(dst_state, dict):
            continue
        ek = str(r.get('event_key', r.get('event', '')) or '').strip().lower()
        vn = str(r.get('var', r.get('var_name', '')) or '').strip()
        if not ek or not vn:
            continue
        try:
            evc = int((src_state.get('_events') or {}).get(ek, 0) or 0)
        except Exception:
            evc = 0
        try:
            thr = int(r.get('only_if_event_gt', 0) or 0)
        except Exception:
            thr = 0
        if evc <= thr:
            continue
        try:
            fac = float(r.get('factor', 1.0) or 1.0)
        except Exception:
            fac = 1.0
        op = str(r.get('op','inc') or 'inc').lower().strip()
        # ensure vars dict
        try:
            vdict = dst_state.get('vars')
            if not isinstance(vdict, dict):
                dst_state['vars'] = {}
                vdict = dst_state['vars']
        except Exception:
            dst_state['vars'] = {}
            vdict = dst_state['vars']
        cur = vdict.get(vn, 0.0)
        try:
            curf = float(cur or 0.0)
        except Exception:
            # toggles supported: treat as 0/1
            curf = 1.0 if bool(cur) else 0.0
        val = float(evc) * float(fac)
        if op == 'set':
            out = val
        elif op in ('dec','sub','-'):
            out = curf - val
        else:
            out = curf + val
        # clamp
        mn = r.get('clamp_min', None)
        mx = r.get('clamp_max', None)
        try:
            if mn is not None:
                out = max(float(mn), out)
        except Exception:
            pass
        try:
            if mx is not None:
                out = min(float(mx), out)
        except Exception:
            pass
        vdict[vn] = out

def _apply_var_var_routes(project, all_states):
    """Apply project-level var->var routing with transforms ().

    Looks for project.data['var_routes'] (preferred) or project.var_routes.
    Route fields (tolerant):
      - src_layer (int), src_var (str)
      - dst_layer (int), dst_var (str)
      - op: set/inc/dec (default set)
      - factor (float, default 1.0)
      - offset (float, default 0.0)
      - clamp_min / clamp_max optional
      - smooth_alpha (0..1) optional (EMA smoothing on the *input*)
      - abs (bool) optional, min/max gate optional: only_if_src_gt / only_if_src_lt
      - id optional (string) for smoothing memory; auto-generated from fields if missing.
    """
    try:
        data = getattr(project, 'data', None)
        if isinstance(project, dict):
            data = project
    except Exception:
        data = {}
    routes = None
    try:
        routes = (data or {}).get('var_routes')
    except Exception:
        routes = None
    if routes is None:
        try:
            routes = getattr(project, 'var_routes', None)
        except Exception:
            routes = None
    if not isinstance(routes, list) or not routes:
        return
    for r in routes:
        if not isinstance(r, dict):
            continue
        try:
            if not bool(r.get('enabled', True)):
                continue
        except Exception:
            pass
        try:
            sL = int(r.get('src_layer', r.get('src', -1)) or -1)
            dL = int(r.get('dst_layer', r.get('dst', -1)) or -1)
        except Exception:
            continue
        if sL < 0 or dL < 0 or sL >= len(all_states) or dL >= len(all_states):
            continue
        src_state = all_states[sL]
        dst_state = all_states[dL]
        if not isinstance(src_state, dict) or not isinstance(dst_state, dict):
            continue
        sv = str(r.get('src_var', r.get('src_name', r.get('var', ''))) or '').strip()
        dv = str(r.get('dst_var', r.get('dst_name', r.get('out', ''))) or '').strip()
        if not sv or not dv:
            continue
        # read source value (number or toggle)
        try:
            sval = (src_state.get('vars') or {}).get(sv, 0.0)
        except Exception:
            sval = 0.0
        try:
            x = float(sval or 0.0)
        except Exception:
            x = 1.0 if bool(sval) else 0.0
        try:
            if bool(r.get('abs', False)):
                x = abs(x)
        except Exception:
            pass
        # gates
        try:
            gt = r.get('only_if_src_gt', None)
            if gt is not None and x <= float(gt):
                continue
        except Exception:
            pass
        try:
            lt = r.get('only_if_src_lt', None)
            if lt is not None and x >= float(lt):
                continue
        except Exception:
            pass
        # smoothing (EMA) on input
        try:
            a = r.get('smooth_alpha', None)
            if a is not None:
                a = float(a)
                if a < 0.0: a = 0.0
                if a > 1.0: a = 1.0
            else:
                a = None
        except Exception:
            a = None
        if a is not None and a > 0.0:
            rid = str(r.get('id','') or '').strip()
            if not rid:
                rid = f"{sL}.{sv}->{dL}.{dv}"
            mem = dst_state.get('_route_mem')
            if not isinstance(mem, dict):
                dst_state['_route_mem'] = {}
                mem = dst_state['_route_mem']
            prev = mem.get(rid, x)
            try:
                prev = float(prev)
            except Exception:
                prev = x
            x = (1.0 - a) * prev + a * x
            mem[rid] = x
        # transform
        try:
            fac = float(r.get('factor', 1.0) or 1.0)
        except Exception:
            fac = 1.0
        try:
            off = float(r.get('offset', 0.0) or 0.0)
        except Exception:
            off = 0.0
        val = x * fac + off
        # clamp
        mn = r.get('clamp_min', None)
        mx = r.get('clamp_max', None)
        try:
            if mn is not None:
                val = max(float(mn), val)
        except Exception:
            pass
        try:
            if mx is not None:
                val = min(float(mx), val)
        except Exception:
            pass
        # write to dst var
        vdict = dst_state.get('vars')
        if not isinstance(vdict, dict):
            dst_state['vars'] = {}
            vdict = dst_state['vars']
        cur = vdict.get(dv, 0.0)
        try:
            curf = float(cur or 0.0)
        except Exception:
            curf = 1.0 if bool(cur) else 0.0
        op = str(r.get('op','set') or 'set').lower().strip()
        if op == 'set':
            out = val
        elif op in ('inc','add','+'):
            out = curf + val
        elif op in ('dec','sub','-'):
            out = curf - val
        else:
            out = val
        vdict[dv] = out

def _apply_param_routes(project, layers, all_states):
    """Apply project-level routes that write into parameters (emitters/forces/layer params) ().

    Looks for project.data['param_routes'] (preferred) or project.param_routes.
    Route fields:
      - src_type: 'event' or 'var' (default 'var')
      - src_layer (int), event_key/src_var (str)
      - dst: string like 'L2.e1.spawn_rate' or 'L0.f0.strength' or 'L3.p.spawn_rate' or 'L1.spawn_rate'
      - op: set/inc/dec (default set)
      - factor/offset/clamp_min/clamp_max optional
    """
    try:
        data = getattr(project, 'data', None)
        if isinstance(project, dict):
            data = project
    except Exception:
        data = {}
    routes = None
    try:
        routes = (data or {}).get('param_routes')
    except Exception:
        routes = None
    if routes is None:
        try:
            routes = getattr(project, 'param_routes', None)
        except Exception:
            routes = None
    if not isinstance(routes, list) or not routes:
        return
    for r in routes:
        if not isinstance(r, dict):
            continue
        try:
            if not bool(r.get('enabled', True)):
                continue
        except Exception:
            pass
        try:
            sL = int(r.get('src_layer', r.get('src', -1)) or -1)
        except Exception:
            sL = -1
        if sL < 0 or sL >= len(all_states):
            continue
        src_state = all_states[sL]
        if not isinstance(src_state, dict):
            continue
        stype = str(r.get('src_type','var') or 'var').lower().strip()
        if stype in ('event','events'):
            ek = str(r.get('event_key', r.get('event', '')) or '').strip().lower()
            if not ek:
                continue
            try:
                x = float((src_state.get('_events') or {}).get(ek, 0) or 0.0)
            except Exception:
                x = 0.0
        else:
            sv = str(r.get('src_var', r.get('var', '')) or '').strip()
            if not sv:
                continue
            try:
                sval = (src_state.get('vars') or {}).get(sv, 0.0)
            except Exception:
                sval = 0.0
            try:
                x = float(sval or 0.0)
            except Exception:
                x = 1.0 if bool(sval) else 0.0
        try:
            fac = float(r.get('factor', 1.0) or 1.0)
        except Exception:
            fac = 1.0
        try:
            off = float(r.get('offset', 0.0) or 0.0)
        except Exception:
            off = 0.0
        val = x * fac + off
        mn = r.get('clamp_min', None)
        mx = r.get('clamp_max', None)
        try:
            if mn is not None: val = max(float(mn), val)
        except Exception:
            pass
        try:
            if mx is not None: val = min(float(mx), val)
        except Exception:
            pass
        dst = str(r.get('dst','') or '').strip()
        if not dst:
            continue
        # parse dst: optional L<idx>.
        dL = None
        rest = dst
        if (rest[:1] in ('L','l')) and '.' in rest:
            head, rest2 = rest.split('.',1)
            try:
                dL = int(head[1:])
                rest = rest2.strip()
            except Exception:
                dL = None
        if dL is None:
            try:
                dL = int(r.get('dst_layer', r.get('dst_layer_index', -1)) or -1)
            except Exception:
                dL = -1
        if dL < 0 or dL >= len(layers):
            continue
        L = layers[dL]
        op = str(r.get('op','set') or 'set').lower().strip()
        # emitter target: e<idx>.<field>
        if rest.startswith('e') and '.' in rest:
            left, field = rest.split('.',1)
            field = field.strip()
            try:
                ei = int(left[1:])
            except Exception:
                continue
            try:
                p = getattr(L, 'params', None)
                if not isinstance(p, dict):
                    p = {}
                    setattr(L, 'params', p)
                ems = p.get('emitters')
                if not isinstance(ems, list):
                    ems = []
                    p['emitters'] = ems
                while len(ems) <= ei:
                    ems.append({'enabled': True, 'spawn_rate': 0.0})
                cur = ems[ei].get(field, 0.0)
                if field == 'enabled':
                    if op == 'toggle':
                        ems[ei][field] = not bool(cur)
                    else:
                        ems[ei][field] = bool(val)
                else:
                    try: curf = float(cur or 0.0)
                    except Exception: curf = 0.0
                    if op in ('inc','add','+'): out = curf + val
                    elif op in ('dec','sub','-'): out = curf - val
                    else: out = val
                    ems[ei][field] = out
            except Exception:
                pass
            continue
        # force target: f<idx>.<field> (runtime forces if present)
        if rest.startswith('f') and '.' in rest:
            left, field = rest.split('.',1)
            field = field.strip()
            try:
                fi = int(left[1:])
            except Exception:
                continue
            try:
                st = getattr(L, '_state', None)
                if isinstance(st, dict):
                    forces = st.get('_forces')
                else:
                    forces = None
                if not isinstance(forces, list):
                    # seed from params
                    p = getattr(L, 'params', {}) or {}
                    srcf = p.get('forces') if isinstance(p, dict) else None
                    forces = copy.deepcopy(srcf) if isinstance(srcf, list) else []
                    if isinstance(st, dict):
                        st['_forces'] = forces
                while len(forces) <= fi:
                    forces.append({'enabled': True})
                cur = forces[fi].get(field, 0.0)
                if field == 'enabled':
                    if op == 'toggle':
                        forces[fi][field] = not bool(cur)
                    else:
                        forces[fi][field] = bool(val)
                else:
                    try: curf = float(cur or 0.0)
                    except Exception: curf = 0.0
                    if op in ('inc','add','+'): out = curf + val
                    elif op in ('dec','sub','-'): out = curf - val
                    else: out = val
                    forces[fi][field] = out
            except Exception:
                pass
            continue
        # layer param target: 'p.<field>' or '<field>'
        field = rest
        if field.startswith('p.'):
            field = field[2:]
        field = field.strip()
        if not field:
            continue
        try:
            p = getattr(L, 'params', None)
            if not isinstance(p, dict):
                p = {}
                setattr(L, 'params', p)
            cur = p.get(field, 0.0)
            if (field in ('enabled',)):
                if op == 'toggle':
                    p[field] = not bool(cur)
                else:
                    p[field] = bool(val)
            else:
                try: curf = float(cur or 0.0)
                except Exception: curf = 0.0
                if op in ('inc','add','+'): out = curf + val
                elif op in ('dec','sub','-'): out = curf - val
                else: out = val
                p[field] = out
        except Exception:
            pass


def _resolve_interactions(layers, *, layout_mw: int, layout_mh: int):
    """Engine-owned cross-layer interaction bus (frame-scoped)."""
    try:
        targets_by_cell = {}
        for li, L in enumerate(layers):
            key = str(_lg(L, "behavior", _lg(L, "effect", ""))).lower().strip()
            beh = REGISTRY.get(key)
            if not beh:
                continue
            gtt = getattr(beh, "get_hit_targets", None)
            if not callable(gtt):
                continue
            params = dict(getattr(L, "params", {}) or {})
            params["_mw"] = int(layout_mw); params["_mh"] = int(layout_mh)
            try:
                tlist = gtt(state=_lg(L, "_state", None), params=params) or []
            except Exception:
                tlist = []
            for td in tlist:
                try:
                    x = int(td.get("x")); y = int(td.get("y"))
                    if 0 <= x < layout_mw and 0 <= y < layout_mh:
                        targets_by_cell.setdefault((x,y), []).append((li, td))
                except Exception:
                    pass

        for li, L in enumerate(layers):
            key = str(_lg(L, "behavior", _lg(L, "effect", ""))).lower().strip()
            beh = REGISTRY.get(key)
            if not beh:
                continue
            ghe = getattr(beh, "get_hit_events", None)
            if not callable(ghe):
                continue
            params = dict(getattr(L, "params", {}) or {})
            params["_mw"] = int(layout_mw); params["_mh"] = int(layout_mh)
            try:
                hits = ghe(state=_lg(L, "_state", None), params=params) or []
            except Exception:
                hits = []
            for hit in hits:
                try:
                    x = int(hit.get("x")); y = int(hit.get("y"))
                except Exception:
                    continue
                for (tli, td) in list(targets_by_cell.get((x,y), []) or []):
                    try:
                        TL = layers[tli]
                        tkey = str(getattr(TL, "behavior", getattr(TL, "effect", ""))).lower().strip()
                        tbeh = REGISTRY.get(tkey)
                        if not tbeh:
                            continue
                        ah = getattr(tbeh, "apply_hit", None)
                        if not callable(ah):
                            continue
                        tparams = dict(getattr(TL, "params", {}) or {})
                        tparams["_mw"] = int(layout_mw); tparams["_mh"] = int(layout_mh)
                        consumed = bool(ah(state=getattr(TL, "_state", None), params=tparams, hit=hit, target=td))
                        if consumed:
                            targets_by_cell[(x,y)] = [(a,b) for (a,b) in targets_by_cell.get((x,y), []) if b is not td]
                            break
                    except Exception:
                        continue
    except Exception:
        pass

class PreviewEngine:
    """Pure preview renderer (no Tkinter).

    - Deterministic fixed-tick simulation clock (for stateful/game layers)
    - render_frame(t) returns list[RGB] length = num_leds
    """

    def __init__(self, project, audio, fixed_dt: float = 1.0 / 60.0, signal_bus=None):
        self.project = project
        try:
            _pd = project.data if hasattr(project,'data') else (project if isinstance(project, dict) else {})
            self._purpose = dict((_pd or {}).get('purpose_values') or {})
        except Exception:
            self._purpose = {}
        self.audio = audio
        # Optional: publish audio/variables into the runtime SignalBus so Rules and diagnostics
        # can observe live values (audio.energy, audio.mono0..6, audio.L0..6, audio.R0..6).
        self.signal_bus = signal_bus
        self.clock = SimClock(fixed_dt=float(fixed_dt))
        self._frame_index = 0
        # Real-time clock snapshot for preview-only 'clock' signals
        self._clock_last_minute = None
        self._clock_last_second = None
        self._last_live_rows = []
        self._last_layer_stats = {}

        # Engine-owned persistent state for stateful/game effects
        self._state_by_uid: Dict[str, EffectState] = {}
        # PostFX per-layer history (trail)
        self._trail_prev_by_uid: Dict[str, List[RGB]] = {}
        self._matrix_neighbors_cache: Optional[List[List[int]]] = None

        # Small LUT caches for per-pixel operators (performance).
        # Keyed by a rounded parameter value to avoid unbounded growth.
        self._gamma_lut_cache: Dict[float, List[int]] = {}

        # Audio analysis caches used to build deterministic "_audio_flat" and "_audio_events"
        # injected into effect params each frame.
        self._audio_prev_flat: Dict[str, float] = {}
        self._audio_prev_energy: float = 0.0

        self.last_error: Optional[str] = None
        self.last_traceback: Optional[str] = None
        self._fps_last_t: float = 0.0
        self._fps_frames: int = 0
        self.fps: float = 0.0
    def render_frame(self, t: float) -> List[RGB]:

        try:
            _prev_sim = float(self.clock.sim_time)
            steps = self.clock.step_to(float(t))
            _dt = float(getattr(self.clock, 'fixed_dt', 1.0/60.0))
            self._frame_index = int(getattr(self, '_frame_index', 0)) + 1


            layout = getattr(self.project, "layout", None)
            shape = getattr(layout, "shape", "strip")
            if shape in ("cells","matrix"):  # matrix uses mw/mh too
                mw = int(getattr(layout, "mw", 16) or 16)
                mh = int(getattr(layout, "mh", 16) or 16)
                n = mw * mh
            else:
                n = int(getattr(layout, "num_leds", 60) or 60)

            # Layout hints (internal): some simulation effects need to know
            # the current grid dimensions, but Behavior preview_emit/update
            # signatures don't include layout.
            #
            # We inject these into params as _mw/_mh (harmless for other effects).
            _layout_mw = mw if shape in ("cells","matrix") else n
            _layout_mh = mh if shape in ("cells","matrix") else 1
            def _lg(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            def _ls(obj, key, value):
                if isinstance(obj, dict):
                    obj[key] = value
                else:
                    setattr(obj, key, value)

            # Provide a consistent layout dict for behaviors that expect mapping-style layout hints.
            _layout_info = {
                'shape': shape,
                'mw': mw if shape == 'cells' else n,
                'mh': mh if shape == 'cells' else 1,
                'num_leds': n,
            }


            out: List[RGB] = [(0, 0, 0)] * n
            # Operators mask resolution cache (per-frame)
            _op_mask_cache: Dict[str, Set[int]] = {}

            # Ensure simulated audio advances with time.
            #
            # A number of audio-reactive effects (and the legacy _audio_events/_audio_tempo
            # shims) depend on the audio state changing over time. If the audio backend is
            # present but never stepped, those effects can appear "BLANK" in Effect Audit
            # even though their renderers are correct.
            try:
                if getattr(self, 'audio', None) is not None and hasattr(self.audio, 'step'):
                    # Use the simulation time (after clock stepping) for determinism.
                    try:
                        _t = float(getattr(self.clock, "sim_time", 0.0))
                    except Exception:
                        _t = 0.0
                    # Avoid redundant stepping at the same timestamp (engine-owned audio may already step).
                    try:
                        _last = getattr(self.audio, "_last_t", None)
                    except Exception:
                        _last = None
                    if _last is None or abs(float(_t) - float(_last)) > 1e-9:
                        self.audio.step(float(_t))
            except Exception:
                pass            # audio sampled at render time (good enough for now; export parity later can sample per tick)
            audio_dict: Dict[str, Any] = {}
            try:
                audio_dict = dict(getattr(self.audio, "state", {}) or {})
            except Exception:
                audio_dict = {}

            # Normalize audio dict so effects can rely on consistent keys.
            audio_dict.setdefault('mode', getattr(self.audio, 'mode', 'sim'))
            audio_dict.setdefault('backend', getattr(self.audio, 'backend', 'sim'))
            audio_dict.setdefault('status', getattr(self.audio, 'status', 'ok'))
            mono = list(audio_dict.get('mono') or [0.0]*7)
            L = list(audio_dict.get('L') or [0.0]*7)
            R = list(audio_dict.get('R') or [0.0]*7)
            if len(mono) < 7: mono += [0.0]*(7-len(mono))
            if len(L) < 7: L += [0.0]*(7-len(L))
            if len(R) < 7: R += [0.0]*(7-len(R))
            audio_dict['mono'] = mono[:7]
            audio_dict['L'] = L[:7]
            audio_dict['R'] = R[:7]
            for i in range(7):
                audio_dict[f'mono{i}'] = float(audio_dict['mono'][i])
                audio_dict[f'L{i}'] = float(audio_dict['L'][i])
                audio_dict[f'R{i}'] = float(audio_dict['R'][i])

            # Publish the normalized audio into the runtime SignalBus so Rules and diagnostics
            # can reference audio.energy / audio.mono0..6 / audio.L0..6 / audio.R0..6.
            # Build preview-only wall clock signals (hour/minute/second + change flags)
            try:
                import datetime as _dtmod
                _now = _dtmod.datetime.now()
                _h = int(_now.hour); _m = int(_now.minute); _s = int(_now.second)
            except Exception:
                _h = 0; _m = 0; _s = 0
            _min_changed = 1 if (getattr(self, '_clock_last_minute', None) is not None and _m != getattr(self, '_clock_last_minute', None)) else 0
            _sec_changed = 1 if (getattr(self, '_clock_last_second', None) is not None and _s != getattr(self, '_clock_last_second', None)) else 0
            self._clock_last_minute = _m
            self._clock_last_second = _s
            _clock_vars = {
                'number': {
                    'clock.hour': float(_h),
                    'clock.minute': float(_m),
                    'clock.second': float(_s),
                    'clock.minute_changed': float(_min_changed),
                    'clock.second_changed': float(_sec_changed),
                }
            }

            _clock_sig = {
                'hour': int(_h),
                'minute': int(_m),
                'second': int(_s),
                'minute_changed': int(_min_changed),
                'second_changed': int(_sec_changed),
            }
            try:
                if isinstance(audio_dict, dict):
                    audio_dict['clock'] = _clock_sig
            except Exception:
                pass

            # IMPORTANT: SignalBus.update() is keyword-only. Positional calls will raise
            # TypeError and silently disable audio/rules diagnostics.
            try:
                if self.signal_bus is not None and hasattr(self.signal_bus, 'update'):
                    self.signal_bus.update(
                        t=float(getattr(self.clock, 'sim_time', 0.0)),
                        dt=float(getattr(self.clock, 'fixed_dt', 1.0/60.0)),
                        frame=int(getattr(self, '_frame_index', 0)),
                        audio_state=audio_dict,
                        variables_state=_clock_vars,
                    )
            except Exception:
                pass

            # Keep a copy for UI/health reporting.
            self.last_audio_state = dict(audio_dict)

            # Canonical flat view + transient events used by several effects.
            # Many "audio-*" effects expect params["_audio_flat"] and params["_audio_events"].
            audio_flat = {f"l{i}": float(audio_dict[f"L{i}"]) for i in range(7)}
            audio_flat.update({f"r{i}": float(audio_dict[f"R{i}"]) for i in range(7)})
            audio_flat.update({f"m{i}": float(audio_dict[f"mono{i}"]) for i in range(7)})
            audio_flat["energy"] = float(audio_dict.get("energy", 0.0) or 0.0)

            audio_events: Dict[str, float] = {}
            # Simple transient: positive delta from previous frame.
            for k, v in audio_flat.items():
                if k == "energy":
                    continue
                prev = float(self._audio_prev_flat.get(k, 0.0))
                # At typical UI frame rates (e.g. ~60fps), raw deltas can be too small
                # to trip effect thresholds. We scale and clamp to yield a usable
                # 0..1 transient signal.
                tr = max(0.0, v - prev)
                audio_events[f"{k}_tr"] = min(1.0, tr * 8.0)
                self._audio_prev_flat[k] = v
            prev_e = float(self._audio_prev_energy)
            e = float(audio_flat["energy"])
            audio_events["energy_tr"] = min(1.0, max(0.0, e - prev_e) * 8.0)
            self._audio_prev_energy = e
            # Convenience semantic events (kick/snare/beat) used by some effects.
            audio_events["kick"] = max(audio_events.get("l0_tr", 0.0), audio_events.get("r0_tr", 0.0))
            audio_events["snare"] = max(audio_events.get("l4_tr", 0.0), audio_events.get("r4_tr", 0.0))
            audio_events["beat"] = audio_events.get("energy_tr", 0.0)

            # If the audio backend provides explicit event pulses (e.g. sim kick/snare/beat),
            # prefer them because scaled deltas may still stay below some effect thresholds.
            try:
                _kick = float(audio_dict.get("kick", 0.0) or 0.0)
                _snare = float(audio_dict.get("snare", 0.0) or 0.0)
                _beat = float(audio_dict.get("beat", 0.0) or 0.0)
                if _kick > 0.0:
                    audio_events["kick"] = max(audio_events.get("kick", 0.0), _kick)
                    audio_events["l0_tr"] = max(audio_events.get("l0_tr", 0.0), _kick)
                    audio_events["r0_tr"] = max(audio_events.get("r0_tr", 0.0), _kick)
                if _snare > 0.0:
                    audio_events["snare"] = max(audio_events.get("snare", 0.0), _snare)
                    audio_events["l4_tr"] = max(audio_events.get("l4_tr", 0.0), _snare)
                    audio_events["r4_tr"] = max(audio_events.get("r4_tr", 0.0), _snare)
                if _beat > 0.0:
                    audio_events["beat"] = max(audio_events.get("beat", 0.0), _beat)
                    audio_events["energy_tr"] = max(audio_events.get("energy_tr", 0.0), _beat)
            except Exception:
                pass

            # If we're running against a smooth audio source (notably AudioSim), the
            # per-frame deltas are tiny (~0.01-0.02). Event-driven effects then render
            # blank because kick/snare/beat never cross their internal thresholds.
            #
            # To keep preview + audit deterministic and useful, synthesize simple
            # periodic pulses when no real events are present.
            try:
                is_sim = (type(self.audio).__name__ == "AudioSim") if (self.audio is not None) else False
                if is_sim and max(float(audio_events.get("kick", 0.0)), float(audio_events.get("snare", 0.0)), float(audio_events.get("beat", 0.0))) < 0.05:
                    # 120 BPM beat grid. Kick on beat, snare on off-beat.
                    bpm = 120.0
                    beat_hz = bpm / 60.0  # 2.0
                    phase = (float(t) * beat_hz) % 1.0
                    pulse = 1.0 if phase < 0.08 else 0.0
                    off = 1.0 if (0.5 <= phase < 0.58) else 0.0

                    audio_events["beat"] = max(float(audio_events.get("beat", 0.0)), pulse)
                    audio_events["energy_tr"] = max(float(audio_events.get("energy_tr", 0.0)), pulse)

                    audio_events["kick"] = max(float(audio_events.get("kick", 0.0)), pulse)
                    audio_events["l0_tr"] = max(float(audio_events.get("l0_tr", 0.0)), pulse)
                    audio_events["r0_tr"] = max(float(audio_events.get("r0_tr", 0.0)), pulse)

                    audio_events["snare"] = max(float(audio_events.get("snare", 0.0)), off)
                    audio_events["l4_tr"] = max(float(audio_events.get("l4_tr", 0.0)), off)
                    audio_events["r4_tr"] = max(float(audio_events.get("r4_tr", 0.0)), off)
            except Exception:
                pass

            layers = list(getattr(self.project, "layers", []) or [])

            # Phase 2.2 Rules MVP: compute per-layer runtime param overrides
            # (do not mutate project/layer saved params).
            rule_overrides = _apply_project_param_rules(self.project, layers, audio_dict, float(t))

            # Precompute targets (groups/zones) for fast masking.
            try:
                _groups = list(getattr(self.project, 'groups', []) or [])
            except Exception:
                _groups = []
            try:
                _zones = list(getattr(self.project, 'zones', []) or [])
            except Exception:
                _zones = []
            try:
                self._last_layer_stats = {}
            except Exception:
                pass

            # Capture moduloted param deltas for UI inspector
            # (Optional; never blocks render or audit)
            try:
                self._last_live_rows = []
            except Exception:
                pass

# Ensure per-layer persistent state exists (engine-owned, keyed by stable layer uid)
            alive_uids: Set[str] = set()
            for _li, L in enumerate(layers):
                # Respect per-layer enable toggle (disabled layers must not render).
                if not _lg(L, 'enabled', True):
                    continue

                uid = str(_lg(L, 'uid', '') or '')
                if not uid:
                    # Fallback: stash uid into params if present, else derive deterministically
                    p = _lg(L, 'params', None)
                    if isinstance(p, dict):
                        uid = str(p.get('__uid') or p.get('uid') or '')
                        if not uid:
                            uid = f"L{_li}:{str(_lg(L, 'behavior', _lg(L, 'effect', '')))}"
                            p['__uid'] = uid
                    else:
                        uid = f"L{_li}:{str(_lg(L, 'behavior', _lg(L, 'effect', '')))}"
                alive_uids.add(uid)
                st = self._state_by_uid.get(uid)
                if st is None:
                    st = EffectState()
                    self._state_by_uid[uid] = st
                _ls(L, '_state', st)
            # Prune orphaned states
            try:
                for k in list(self._state_by_uid.keys()):
                    if k not in alive_uids:
                        self._state_by_uid.pop(k, None)
            except Exception:
                pass

            # Fixed-tick updates for stateful/game layers (deterministic)
            if steps > 0:
                _dt = float(getattr(self.clock, 'fixed_dt', 1.0/60.0))
                for _si in range(int(steps)):
                    sim_t = float(_prev_sim + (_si + 1) * _dt)
                    # : cross-layer rule targeting (expose all layer states)
                    all_states = [_lg(_L, '_state', None) for _L in layers]
                    for _li, L in enumerate(layers):
                        if not bool(_lg(L, "enabled", True)):
                            continue
                        key = str(_lg(L, "behavior", _lg(L, "effect", ""))).lower().strip()
                        beh = REGISTRY.get(key)
                        is_stateful = bool(getattr(beh, "stateful", False)) or (
                            callable(getattr(beh, "state_init", None))
                            or callable(getattr(beh, "state_tick", None))
                            or callable(getattr(beh, "state_apply_to_params", None))
                        )
                        if not beh or not is_stateful:
                            continue
                        upd = getattr(beh, "update", None)
                        if not callable(upd):
                            upd = None

                        base_params = {}

                        base_params = ensure_params(dict(_lg(L, "params", {}) or {}), beh.uses or [])
                        # Inject canonical audio views for audio-reactive stateful behaviors.
                        base_params["_audio_flat"] = dict(audio_flat)
                        base_params["_audio_events"] = dict(audio_events)
                        try:
                            if _li < len(rule_overrides) and isinstance(rule_overrides[_li], dict):
                                base_params.update(rule_overrides[_li])
                        except Exception:
                            pass
                        base_params["_mw"] = _layout_mw
                        base_params["_mh"] = _layout_mh                        # : pass per-effect variables + rules into params for stateful behaviors
                        try:
                            base_params["_vars_def"] = list(_lg(L, "variables", []) or [])
                        except Exception:
                            try:
                                base_params["_vars_def"] = list((_lg(L, "data", {}) or {}).get("variables", []) or [])
                            except Exception:
                                base_params["_vars_def"] = []

                        try:
                            base_params["_rules"] = list(_lg(L, "rules", []) or [])
                        except Exception:
                            try:
                                base_params["_rules"] = list((_lg(L, "data", {}) or {}).get("rules", []) or [])
                            except Exception:
                                base_params["_rules"] = []

                        # Support both canonical per-layer key ('modulotors') and the legacy key ('mods').
                        mods_raw = _lg(L, "modulotors", None)
                        if mods_raw is None:
                            mods_raw = _lg(L, "mods", [])
                        mods = _normalize_modulotors(list(mods_raw or []))
                        audio_ctx = dict(audio_dict or {})
                        try:
                            params = resolve(base_params, sim_t, audio=audio_ctx, modulotors=mods)
                            # : provide layer states + index for cross-layer actions
                            try:
                                params['_all_states'] = list(all_states)
                                params['_layer_index'] = int(_li)
                            except Exception:
                                pass

                        except Exception:
                            params = dict(base_params) if 'base_params' in locals() else {}

                        # Provide deterministic layout/timing hints to stateful updates.
                        try:
                            params['_num_leds'] = int(n)
                            params['_mw'] = int(_layout_mw)
                            params['_mh'] = int(_layout_mh)
                            params['_fixed_dt'] = _dt
                        except Exception:
                            pass

                        if upd is not None:
                            try:
                                upd(state=_lg(L, "_state", {}), params=params, dt=_dt, t=sim_t, audio=audio_dict)
                            except Exception:
                                pass
                        else:
                            # Legacy/state-hook path (used by purpose_autoplay and other stateful preview-only behaviors).
                            # The contract is: state_init(params)->state, state_tick(state, dt, params),
                            # state_apply_to_params(state, params) before preview_emit.
                            try:
                                st = _lg(L, "_state", {})
                                if not st and callable(getattr(beh, "state_init", None)):
                                    st.update(getattr(beh, "state_init")(params) or {})
                                if callable(getattr(beh, "state_tick", None)):
                                    getattr(beh, "state_tick")(st, _dt, params)
                                if callable(getattr(beh, "state_apply_to_params", None)):
                                    getattr(beh, "state_apply_to_params")(st, params)
                            except Exception:
                                pass

            # : project-level event->var routing table (wires)
            try:
                _apply_event_var_routes(self.project, layers, all_states)
            except Exception:
                pass

            # : project-level var->var routing table (transforms / smoothing)
            try:
                _apply_var_var_routes(self.project, all_states)
            except Exception:
                pass

            # : project-level param routing (vars/events -> emitters/forces/params)
            try:
                _apply_param_routes(self.project, layers, all_states)
            except Exception:
                pass

            # SHOWCASE COMPLETION FLASH (Breakout+Invaders):
            # If BOTH bricks and invaders are cleared, flash blue for ~2s then reset both layers.
            try:
                if shape == "cells":
                    breakout_layer = None
                    inv_layer = None
                    for _li, _L in enumerate(layers):
                        _key = str(getattr(_L, "behavior", getattr(_L, "effect", ""))).lower().strip()
                        if _key == "breakout_game":
                            breakout_layer = _L
                        elif _key == "space_invaders_game":
                            inv_layer = _L
                    if breakout_layer is not None and inv_layer is not None:
                        bstate = getattr(breakout_layer, "_state", None) or {}
                        istate = getattr(inv_layer, "_state", None) or {}
                        bricks = bstate.get("bricks")
                        if bricks is None:
                            bricks = {}
                        # cleared if empty OR no remaining health
                        try:
                            bricks_cleared = (len(bricks) == 0) or (not any(int(h) > 0 for h in bricks.values()))
                        except Exception:
                            bricks_cleared = True
                        invs = istate.get("invaders")
                        if invs is None:
                            invs = []
                        invaders_cleared = (len(invs) == 0)

                        if bricks_cleared and invaders_cleared:
                            if float(self._showcase_flash_until) <= 0.0:
                                self._showcase_flash_until = float(t) + 2.0
                                self._showcase_pending_reset = True

                        # If flash window expired and pending reset, reset both sims once.
                        if self._showcase_pending_reset and float(self._showcase_flash_until) > 0 and float(t) >= float(self._showcase_flash_until):
                            try:
                                if hasattr(breakout_layer, "_state") and isinstance(breakout_layer._state, dict):
                                    breakout_layer._state.clear()
                                if hasattr(inv_layer, "_state") and isinstance(inv_layer._state, dict):
                                    inv_layer._state.clear()
                            except Exception:
                                pass
                            self._showcase_pending_reset = False
                            self._showcase_flash_until = 0.0
            except Exception:
                pass

            # Cross-layer interactions (frame-scoped)
            try:
                if shape == "cells":
                    _resolve_interactions(layers, layout_mw=int(_layout_mw), layout_mh=int(_layout_mh))
            except Exception as _e:
                # Uncomment for debugging:
                # print('interaction bus error', _e)
                pass

            # Render pass

            # : cross-layer rule targeting (expose all layer states)
            all_states = [_lg(_L, '_state', None) for _L in layers]
            for _li, L in enumerate(layers):
                if not bool(_lg(L, "enabled", True)):
                    continue
                key = str(_lg(L, "behavior", _lg(L, "effect", ""))).lower().strip()
                beh = REGISTRY.get(key)
                if not beh:
                    continue

                base_params = ensure_params(dict(_lg(L, "params", {}) or {}), beh.uses or [])
                try:
                    if _li < len(rule_overrides) and isinstance(rule_overrides[_li], dict):
                        base_params.update(rule_overrides[_li])
                except Exception:
                    pass
                # Internal layout hints for simulation effects
                base_params["_mw"] = _layout_mw
                base_params["_mh"] = _layout_mh

                # : pass per-effect variables + rules into params for stateful behaviors
                try:
                    base_params["_vars_def"] = list(_lg(L, "variables", []) or [])
                except Exception:
                    try:
                        base_params["_vars_def"] = list((getattr(L, "data", {}) or {}).get("variables", []) or [])
                    except Exception:
                        base_params["_vars_def"] = []
                try:
                    base_params["_rules"] = list(_lg(L, "rules", []) or [])
                except Exception:
                    try:
                        base_params["_rules"] = list((getattr(L, "data", {}) or {}).get("rules", []) or [])
                    except Exception:
                        base_params["_rules"] = []

                mods_raw = _lg(L, "modulotors", None)
                if mods_raw is None:
                    mods_raw = _lg(L, "mods", [])
                mods = _normalize_modulotors(list(mods_raw or []))
                layer_audio = dict(audio_dict or {})

                try:
                    stdata = getattr(L, '_state', None)
                    if isinstance(stdata, dict):
                        pur = stdata.get('purpose')
                        if isinstance(pur, dict):
                            fl = pur.get('f')
                            il = pur.get('i')
                            if isinstance(fl, list):
                                for idx in range(min(4, len(fl))):
                                    try:
                                        layer_audio[f'purpose_f{idx}'] = max(0.0, min(1.0, float(fl[idx])))
                                    except Exception:
                                        pass
                            if isinstance(il, list):
                                for idx in range(min(4, len(il))):
                                    try:
                                        layer_audio[f'purpose_i{idx}'] = max(0.0, min(1.0, (float(il[idx]) + 1000.0) / 2000.0))
                                    except Exception:
                                        pass
                        for k in ('purpose_f0','purpose_f1','purpose_f2','purpose_f3','purpose_i0','purpose_i1','purpose_i2','purpose_i3'):
                            if k in stdata:
                                try:
                                    layer_audio[k] = max(0.0, min(1.0, float(stdata.get(k))))
                                except Exception:
                                    pass
                        sc = float(stdata.get('score', 0.0) or 0.0)
                        layer_audio['purpose_score'] = max(0.0, min(1.0, sc / 100.0))
                        bl = None
                        if isinstance(stdata.get('blocks'), list):
                            bl = sum(1 for v in stdata.get('blocks') if int(v) > 0)
                        if bl is not None:
                            layer_audio['purpose_blocks_left'] = max(0.0, min(1.0, float(bl) / 8.0))
                except Exception:
                    pass
                audio_ctx = dict(layer_audio or {})
                for k,v in (self._purpose or {}).items():
                    if k.startswith('purpose_'):
                        audio_ctx[k]=v
                sim_t = float(getattr(self.clock, 'sim_time', t))
                params = resolve(base_params, sim_t, audio=audio_ctx, modulotors=mods)
                # : provide layer states + index for cross-layer actions
                try:
                    params['_all_states'] = list(all_states)
                    params['_layer_index'] = int(_li)
                except Exception:
                    pass


                # : Resolve target mask (supports composed ops in Phase A1)
                self._mask_indices = None
                try:
                    if self.project and self.target_mask:
                        n = None
                        try:
                            # best-effort LED count from mapping
                            n = int(getattr(self.mapping, 'count', None) or getattr(self.mapping, 'num_pixels', None) or 0) or None
                        except Exception:
                            n = None
                        idxs = resolve_mask_to_indices(self.project, self.target_mask, n=n)
                        self._mask_indices = sorted(list(idxs))
                except Exception:
                    # Never crash preview due to mask resolution issues
                    self._mask_indices = None
                mask: Optional[Set[int]] = None
                try:
                    tk = str(getattr(L, 'target_kind', 'all') or 'all').lower().strip()
                    tr = int(getattr(L, 'target_ref', 0) or 0)
                    if tk == 'group':
                        if 0 <= tr < len(_groups):
                            g = _groups[tr]
                            idxs = getattr(g, 'indices', None)
                            if idxs is None and isinstance(g, dict):
                                idxs = g.get('indices')
                            if isinstance(idxs, list):
                                mask = {int(i) for i in idxs if isinstance(i, int) or str(i).isdigit()}
                    elif tk == 'zone':
                        if 0 <= tr < len(_zones):
                            z = _zones[tr]
                            start = getattr(z, 'start', None); end = getattr(z, 'end', None)
                            if start is None and isinstance(z, dict):
                                start = z.get('start', 0)
                            if end is None and isinstance(z, dict):
                                end = z.get('end', -1)
                            try:
                                s = int(start or 0)
                                e = int(end if end is not None else -1)
                                if e >= s:
                                    s = max(0, min(n - 1, s))
                                    e = max(0, min(n - 1, e))
                                    if e >= s:
                                        mask = set(range(s, e + 1))
                            except Exception:
                                pass
                    else:
                        mask = None
                except Exception:
                    mask = None

                # Apply Phase A1 target_mask (composed masks) as an additional mask layer
                try:
                    if getattr(self, '_mask_indices', None):
                        m2 = set(int(x) for x in (self._mask_indices or []) if isinstance(x, int) or str(x).isdigit())
                        if mask is None:
                            mask = m2
                        else:
                            mask = set(mask).intersection(m2)
                except Exception:
                    pass

                # Emit this layer's frame (supports stateless + stateful behaviors)
                try:
                    layer_opacity = float(_lg(L, "opacity", 1.0) or 1.0)
                except Exception:
                    layer_opacity = 1.0
                layer_opacity = max(0.0, min(1.0, layer_opacity))
                blend = str(_lg(L, "blend_mode", "over") or "over").lower().strip()
                # Optional per-layer color-key transparency (used by showcases).
                # If params['transparent_key'] is set to an RGB triplet, pixels matching it
                # will be treated as transparent during compositing.
                tkey = None
                try:
                    tkey = params.get('transparent_key', None)
                    if isinstance(tkey, (list, tuple)) and len(tkey) == 3:
                        tkey = (int(tkey[0]) & 255, int(tkey[1]) & 255, int(tkey[2]) & 255)
                    else:
                        tkey = None
                except Exception:
                    tkey = None
                # Inject canonical audio views expected by audio-reactive effects.
                # This keeps effect code simple and makes the audit harness deterministic.
                try:
                    params["_audio_flat"] = dict(audio_flat)
                    params["_audio_events"] = dict(audio_events)
                except Exception:
                    pass
                # Stateful behaviors often compute derived params (e.g. purpose_* signals)
                # during their state_tick. Re-apply those derived params here so the
                # stateless emitters see the updated values.
                try:
                    if callable(getattr(beh, 'state_apply_to_params', None)):
                        beh.state_apply_to_params(_lg(L, "_state", {}), params)
                except Exception:
                    pass
                try:
                    frame = _call_preview_emit(
                        beh,
                        num_leds=int(n),
                        params=params,
                        t=float(sim_t),
                        state=_lg(L, "_state", {}),
                        layout={"shape": shape, "mw": int(_layout_mw), "mh": int(_layout_mh), "count": int(n)},
                        dt=float(_dt),
                        audio=dict(audio_dict or {}),
                    )
                except Exception:
                    frame = [(0, 0, 0)] * int(n)

                # Normalise frame length
                if not isinstance(frame, list):
                    frame = [(0, 0, 0)] * int(n)
                if len(frame) < int(n):
                    frame = list(frame) + [(0, 0, 0)] * (int(n) - len(frame))
                elif len(frame) > int(n):
                    frame = list(frame)[: int(n)]


                # Operators/PostFX MVP (Phase O1/O2): apply per-layer operators BEFORE blending.
                # Contract: L.operators is a list of dicts: {'type': str, 'params': dict}
                try:
                    ops = _lg(L, 'operators', None)
                    if isinstance(ops, list) and ops:
                        for op in ops:
                            try:
                                if not isinstance(op, dict):
                                    continue
                                if bool(op.get('enabled', True)) is False:
                                    continue
                                otype = str(op.get('type', '') or '').lower().strip()
                                params_op = op.get('params') if isinstance(op.get('params'), dict) else {}
                                
                                # Optional per-operator targeting:
                                # Supports: All / Mask / Zone / Group.
                                # Backwards compat: op['mask'] implies Mask targeting.
                                _op_t_kind = None
                                _op_t_key = None
                                try:
                                    _op_t_kind = op.get('target_kind', None)
                                    _op_t_key = op.get('target_key', None)
                                except Exception:
                                    _op_t_kind = None
                                    _op_t_key = None

                                # Back-compat
                                if not _op_t_kind:
                                    try:
                                        mk = op.get('mask', None)
                                        if isinstance(mk, str) and mk.strip():
                                            _op_t_kind = 'mask'
                                            _op_t_key = mk.strip()
                                    except Exception:
                                        pass
                                if not _op_t_kind:
                                    try:
                                        mk = params_op.get('mask', None)
                                        if isinstance(mk, str) and mk.strip():
                                            _op_t_kind = 'mask'
                                            _op_t_key = mk.strip()
                                    except Exception:
                                        pass

                                kind = (str(_op_t_kind or '')).lower().strip()
                                key = (str(_op_t_key or '')).strip()
                                if kind in ('', 'all'):
                                    kind = 'all'
                                    key = ''

                                _op_target_set = None
                                # Layer-target: use this layer's resolved mask (after target_mask intersection)
                                if kind == 'layer':
                                    try:
                                        _op_target_set = set(mask) if mask is not None else None
                                    except Exception:
                                        _op_target_set = None

                                try:
                                    cache_key = (kind, key)
                                    if kind != 'all' and key:
                                        if cache_key in _op_mask_cache:
                                            _op_target_set = _op_mask_cache.get(cache_key)
                                        else:
                                            s = set()
                                            if kind == 'mask':
                                                try:
                                                    from app.masks_resolver import resolve_mask_to_indices
                                                    s = set(resolve_mask_to_indices(pd, key, n=int(n)))
                                                except Exception:
                                                    s = set()
                                            elif kind == 'zone':
                                                try:
                                                    zd = (pd.get('zones') or {})
                                                    z = zd.get(key) if isinstance(zd, dict) else None
                                                    if isinstance(z, dict):
                                                        idx = z.get('indices')
                                                        if isinstance(idx, list):
                                                            s = set(int(x) for x in idx)
                                                        else:
                                                            st = z.get('start'); en = z.get('end')
                                                            if st is not None and en is not None:
                                                                st = int(st); en = int(en)
                                                                lo, hi = (st, en) if st <= en else (en, st)
                                                                s = set(range(lo, hi + 1))
                                                except Exception:
                                                    s = set()
                                            elif kind == 'group':
                                                try:
                                                    gd = (pd.get('groups') or {})
                                                    g = gd.get(key) if isinstance(gd, dict) else None
                                                    if isinstance(g, dict):
                                                        idx = g.get('indices')
                                                        if isinstance(idx, list):
                                                            s = set(int(x) for x in idx)
                                                        else:
                                                            st = g.get('start'); en = g.get('end')
                                                            if st is not None and en is not None:
                                                                st = int(st); en = int(en)
                                                                lo, hi = (st, en) if st <= en else (en, st)
                                                                s = set(range(lo, hi + 1))
                                                except Exception:
                                                    s = set()
                                            _op_target_set = s
                                            _op_mask_cache[cache_key] = _op_target_set
                                except Exception:
                                    _op_target_set = None
                                # If we have an explicit empty target set, this operator affects no pixels.
                                if _op_target_set is not None and len(_op_target_set) == 0:
                                    continue
                                if otype == 'gain':
                                        g = float(params_op.get('gain', 1.0) or 1.0)
                                        if abs(g - 1.0) < 1e-6:
                                            continue
                                        if g < 0.0: g = 0.0
                                        if g > 5.0: g = 5.0
                                        fr2 = list(frame)
                                        if _op_target_set is None:
                                            for ii,(rr,gg,bb) in enumerate(frame):
                                                fr2[ii]=(max(0, min(255, int(rr * g))), max(0, min(255, int(gg * g))), max(0, min(255, int(bb * g))))
                                        else:
                                            for ii in _op_target_set:
                                                if 0 <= ii < len(frame):
                                                    rr,gg,bb = frame[ii]
                                                    fr2[ii]=(max(0, min(255, int(rr * g))), max(0, min(255, int(gg * g))), max(0, min(255, int(bb * g))))
                                        frame = fr2
                                elif otype == 'gamma':
                                            try:
                                                gam = float(params_op.get('gamma', 1.0) or 1.0)
                                            except Exception:
                                                gam = 1.0
                                            if gam < 0.05: gam = 0.05
                                            if gam > 8.0: gam = 8.0
                                            if abs(gam - 1.0) < 1e-6:
                                                continue
                                            # Use a small cached LUT for performance on large LED counts.
                                            gkey = round(float(gam), 3)
                                            lut = self._gamma_lut_cache.get(gkey)
                                            if lut is None:
                                                inv255 = 1.0 / 255.0
                                                lut = [int(max(0, min(255, round(255.0 * ((i * inv255) ** gam))))) for i in range(256)]
                                                # keep cache small
                                                if len(self._gamma_lut_cache) > 32:
                                                    try:
                                                        self._gamma_lut_cache.clear()
                                                    except Exception:
                                                        pass
                                                self._gamma_lut_cache[gkey] = lut
                                            fr2 = list(frame)
                                            if _op_target_set is None:
                                                for ii,(rr,gg,bb) in enumerate(frame):
                                                    fr2[ii]=(lut[int(rr) & 255], lut[int(gg) & 255], lut[int(bb) & 255])
                                            else:
                                                for ii in _op_target_set:
                                                    if 0 <= ii < len(frame):
                                                        rr,gg,bb = frame[ii]
                                                        fr2[ii]=(lut[int(rr) & 255], lut[int(gg) & 255], lut[int(bb) & 255])
                                            frame = fr2
                                elif otype == 'clamp':
                                            try:
                                                cmin = float(params_op.get('clamp_min', 0.0) or 0.0)
                                            except Exception:
                                                cmin = 0.0
                                            try:
                                                cmax = float(params_op.get('clamp_max', 255.0) or 255.0)
                                            except Exception:
                                                cmax = 255.0
                                            if cmin < 0.0: cmin = 0.0
                                            if cmax > 255.0: cmax = 255.0
                                            if cmax < cmin: cmin, cmax = cmax, cmin
                                            imin = int(cmin); imax=int(cmax)
                                            if imin <= 0 and imax >= 255:
                                                continue
                                            fr2 = list(frame)
                                            def _c(v):
                                                v=int(v)
                                                return max(imin, min(imax, v))
                                            if _op_target_set is None:
                                                for ii,(rr,gg,bb) in enumerate(frame):
                                                    fr2[ii]=(_c(rr), _c(gg), _c(bb))
                                            else:
                                                for ii in _op_target_set:
                                                    if 0 <= ii < len(frame):
                                                        rr,gg,bb = frame[ii]
                                                        fr2[ii]=(_c(rr), _c(gg), _c(bb))
                                            frame = fr2
                                elif otype == 'posterize':
                                                try:
                                                    lv = float(params_op.get('posterize_levels', 6.0) or 6.0)
                                                except Exception:
                                                    lv = 6.0
                                                levels = int(lv)
                                                if levels < 2: levels = 2
                                                if levels > 64: levels = 64
                                                step = 255.0 / float(levels - 1)
                                                fr2 = list(frame)
                                                def _p(v):
                                                    v = max(0, min(255, int(v)))
                                                    return int(max(0, min(255, round(round(v / step) * step))))
                                                if _op_target_set is None:
                                                    for ii,(rr,gg,bb) in enumerate(frame):
                                                        fr2[ii]=(_p(rr), _p(gg), _p(bb))
                                                else:
                                                    for ii in _op_target_set:
                                                        if 0 <= ii < len(frame):
                                                            rr,gg,bb = frame[ii]
                                                            fr2[ii]=(_p(rr), _p(gg), _p(bb))
                                                frame = fr2
                                elif otype == 'threshold':
                                        try:
                                            thr = float(params_op.get('threshold', 128.0) or 128.0)
                                        except Exception:
                                            thr = 128.0
                                        if thr < 0.0: thr = 0.0
                                        if thr > 255.0: thr = 255.0
                                        ith = int(thr)
                                        fr2 = list(frame)
                                        def _t(v):
                                            v = max(0, min(255, int(v)))
                                            return 255 if v >= ith else 0
                                        if _op_target_set is None:
                                            for ii,(rr,gg,bb) in enumerate(frame):
                                                fr2[ii]=(_t(rr), _t(gg), _t(bb))
                                        else:
                                            for ii in _op_target_set:
                                                if 0 <= ii < len(frame):
                                                    rr,gg,bb = frame[ii]
                                                    fr2[ii]=(_t(rr), _t(gg), _t(bb))
                                        frame = fr2
                                elif otype == 'invert':
                                        # Invert RGB channels.
                                        fr2 = list(frame)
                                        if _op_target_set is None:
                                            for ii, (rr, gg, bb) in enumerate(frame):
                                                fr2[ii] = (255 - int(rr), 255 - int(gg), 255 - int(bb))
                                        else:
                                            for ii in _op_target_set:
                                                if 0 <= ii < len(frame):
                                                    rr, gg, bb = frame[ii]
                                                    fr2[ii] = (255 - int(rr), 255 - int(gg), 255 - int(bb))
                                        frame = fr2
                                # 'solid' is the base behavior, ignore if present here
                            except Exception:
                                continue
                except Exception:
                    pass
                new_out: List[RGB] = []
                for i, (or_, og, ob) in enumerate(out):
                    if mask is not None and i not in mask:
                        new_out.append((or_, og, ob))
                        continue
                    try:
                        lr, lg, lb = frame[i]
                    except Exception:
                        lr, lg, lb = (0, 0, 0)
                    lr = int(lr) & 255
                    lg = int(lg) & 255
                    lb = int(lb) & 255

                    # Color-key transparency: if this layer emits the key color, keep underlying pixel.
                    if tkey is not None and (lr, lg, lb) == tkey:
                        new_out.append((or_, og, ob))
                        continue

                    if blend == "add":
                        nr = min(255, int(or_ + lr * layer_opacity))
                        ng = min(255, int(og + lg * layer_opacity))
                        nb = min(255, int(ob + lb * layer_opacity))
                    elif blend == "max":
                        nr = max(or_, int(lr * layer_opacity))
                        ng = max(og, int(lg * layer_opacity))
                        nb = max(ob, int(lb * layer_opacity))
                    elif blend == "multiply":
                        nr = int((or_ * (lr / 255.0)) * layer_opacity + or_ * (1.0 - layer_opacity))
                        ng = int((og * (lg / 255.0)) * layer_opacity + og * (1.0 - layer_opacity))
                        nb = int((ob * (lb / 255.0)) * layer_opacity + ob * (1.0 - layer_opacity))
                    elif blend == "screen":
                        def _screen(a, b):
                            return 255 - int((255 - a) * (255 - b) / 255.0)
                        sr = _screen(or_, lr)
                        sg = _screen(og, lg)
                        sb = _screen(ob, lb)
                        nr = int(sr * layer_opacity + or_ * (1.0 - layer_opacity))
                        ng = int(sg * layer_opacity + og * (1.0 - layer_opacity))
                        nb = int(sb * layer_opacity + ob * (1.0 - layer_opacity))
                    else:
                        # over
                        nr = int(or_ * (1.0 - layer_opacity) + lr * layer_opacity)
                        ng = int(og * (1.0 - layer_opacity) + lg * layer_opacity)
                        nb = int(ob * (1.0 - layer_opacity) + lb * layer_opacity)

                    new_out.append((max(0, min(255, nr)), max(0, min(255, ng)), max(0, min(255, nb))))

                out = new_out


            # PostFX (Phase 7A foundation)
            try:
                from preview.postfx import apply_postfx, build_matrix_neighbors
                pf = getattr(self.project, 'postfx', None)
                lay = getattr(self.project, 'layout', None)
                if isinstance(lay, dict):
                    layout = lay
                else:
                    layout = {
                        'shape': getattr(lay, 'shape', None),
                        'num_leds': getattr(lay, 'num_leds', None),
                        'mw': getattr(lay, 'matrix_w', None),
                        'mh': getattr(lay, 'matrix_h', None),
                        'coords': getattr(lay, 'coords', None),
                    }
                shape = str((layout.get('shape') or '')).lower().strip()
                # Cache neighbors for cells layout (rebuild only when coords change)
                if shape == 'cells':
                    coords = layout.get('coords')
                    sig = (len(coords) if isinstance(coords, list) else 0,
                           coords[0] if isinstance(coords, list) and coords else None,
                           coords[-1] if isinstance(coords, list) and coords else None)
                    if sig != self._postfx_layout_sig:
                        self._postfx_neighbors = build_matrix_neighbors(layout, radius=int((pf or {}).get('bleed_radius', 1) or 1))
                        self._postfx_layout_sig = sig
                out, self._postfx_prev = apply_postfx(out, layout=layout, postfx=pf, prev=self._postfx_prev, neighbors=self._postfx_neighbors)
            except Exception:
                pass

            # update preview fps stats
            try:
                now = float(t)
                if self._fps_last_t <= 0.0:
                    self._fps_last_t = now
                    self._fps_frames = 0
                self._fps_frames += 1
                dt = now - self._fps_last_t
                if dt >= 0.5:
                    self.fps = self._fps_frames / max(1e-6, dt)
                    self._fps_last_t = now
                    self._fps_frames = 0
            except Exception:
                pass
            # clear error if we rendered successfully
            self.last_error = None
            self.last_traceback = None
            # Phase A1 global target_mask enforcement: ensure masked-out pixels are black in final output
            # (single choke point; layers already respect mask during blend, but PostFX could otherwise touch all pixels).
            try:
                if getattr(self, '_mask_indices', None):
                    allow = set(int(x) for x in (self._mask_indices or []) if isinstance(x, int) or str(x).isdigit())
                    if allow:
                        out = [rgb if i in allow else (0, 0, 0) for i, rgb in enumerate(out)]
            except Exception:
                pass

            # --- diagnostics: last render stats ---
            try:
                nz = 0
                for _px in (out or []):
                    if _px[0] or _px[1] or _px[2]:
                        nz += 1
                self._last_render_stats = {
                    'ts': __import__('time').time(),
                    'led_count': int(n) if 'n' in locals() else (len(out) if out is not None else None),
                    'layout_shape': str(layout.get('shape') if isinstance(layout, dict) else ''),
                    'layers_n': len(layers) if 'layers' in locals() else None,
                    'nonzero': nz,
                    'last_error': str(getattr(self, '_last_error', '') or ''),
                }
            except Exception:
                pass

            return out
        except Exception as e:
            # Never crash the app from preview; record error and return a safe black frame.
            try:
                self.last_error = f"{type(e).__name__}: {e}"
                self.last_traceback = traceback.format_exc()
            except Exception:
                pass
            # Try to infer LED count to return correct-sized buffer.
            n = 60
            try:
                layout = getattr(self.project, "layout", None)
                shape = getattr(layout, "shape", "strip")
                if shape == "cells":
                    mw = int(getattr(layout, "mw", 16) or 16)
                    mh = int(getattr(layout, "mh", 16) or 16)
                    n = mw * mh
                else:
                    n = int(getattr(layout, "num_leds", 60) or 60)
            except Exception:
                n = 60
            return [(0, 0, 0)] * int(n)


def get_layer_state(self, layer_id: str) -> dict:
        """Return a shallow copy of the layer's runtime state dict (preview-only)."""
        try:
            for L in (self.layers or []):
                if str(getattr(L, 'id', None)) == str(layer_id):
                    st = getattr(L, '_state', None)
                    return dict(st) if isinstance(st, dict) else {}
        except Exception:
            pass
        return {}

def get_runtime_stats(self, layer_id: str) -> dict:
    """Return small, UI-friendly runtime stats for a layer (preview only).
    Safe: never throws, returns {} if unavailable.
    """
    try:
        st = self._state_map.get(str(layer_id))
        if st is None:
            return {}
        # Prefer effect-provided state dict if stateful
        data = getattr(st, "data", None)
        out = {}
        if isinstance(data, dict):
            # common keys
            for k in ("score","health","ammo","cool","cooldown","lives"):
                if k in data:
                    out[k] = data.get(k)
            # breakout stores blocks list
            if "blocks" in data and isinstance(data.get("blocks"), list):
                out["blocks_left"] = sum(1 for v in data["blocks"] if int(v) > 0)
        # --- diagnostics: layer signature / enable flags ---
        try:
            _sig = []
            _en = 0
            for _li, _layer in enumerate((layers or [])):
                if not isinstance(_layer, dict):
                    continue
                _enabled = bool(_layer.get('enabled', True))
                if _enabled:
                    _en += 1
                _sig.append({
                    'i': _li,
                    'id': _layer.get('id', None),
                    'name': _layer.get('name', None),
                    'effect': _layer.get('effect', _layer.get('behavior', None)),
                    'enabled': _enabled,
                    'opacity': _layer.get('opacity', None),
                    'blend': _layer.get('blend', _layer.get('blend_mode', None)),
                })
            self._last_layers_signature = {'enabled_n': _en, 'layers': _sig}
        except Exception:
            pass

        return out
    except Exception:
        return {}


def get_live_params(self):
    """Rows for moduloted params, captured during last render_frame."""
    try:
        return list(self._last_live_rows or [])
    except Exception:
        return []


def get_layer_stats(self):
    """Return last per-layer stats from render_frame (energy / any nonzero)."""
    try:
        return dict(self._last_layer_stats or {})
    except Exception:
        return {}