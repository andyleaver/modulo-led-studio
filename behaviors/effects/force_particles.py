from __future__ import annotations

"""Force Particles (Full-Control primitive).

This is a simulation building block that gives users a core primitive they need
for "light simulations": moving objects + forces (attract/repel).

It is intentionally simple and deterministic:
  - Spawns N particles inside layout bounds
  - Applies a single force toward the playfield center (attract or repel)
  - Optional friction
  - Optional edge wrapping

Later we can extend this to:
  - multiple force sources
  - pairwise repel (separation)
  - force sources driven by variables / audio / selection anchors
"""

from typing import List, Tuple
import math
import copy

from behaviors.registry import BehaviorDef, register
from behaviors.state import EffectState
from behaviors.state_runtime import DeterministicRNG, clamp

RGB = Tuple[int, int, int]

# ----------------------------- : Variables + Rules helpers
def _sanitize_var_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "var"
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        elif ch.isspace():
            out.append("_")
    s = "".join(out).strip("_")
    if not s:
        s = "var"
    # avoid leading digit
    if s[0].isdigit():
        s = "v_" + s
    return s

def _sync_variables(state: EffectState, defs) -> None:
    """Ensure state['vars'] matches current variable definitions."""
    if not isinstance(state, dict):
        return
    if not isinstance(defs, list):
        defs = []
    sig = repr(defs)
    if state.get('_vars_sig') == sig and isinstance(state.get('vars'), dict):
        return
    vars_d = state.get('vars')
    if not isinstance(vars_d, dict):
        vars_d = {}
    meta_d = {}
    # build set of names
    names = []
    for vd in defs:
        if not isinstance(vd, dict):
            continue
        nm = _sanitize_var_name(str(vd.get('name','')))
        vtype = str(vd.get('type','number')).lower().strip()
        if vtype not in ('number','toggle'):
            vtype = 'number'
        if nm in names:
            # de-dupe
            base = nm
            k = 2
            while f"{base}{k}" in names:
                k += 1
            nm = f"{base}{k}"
        names.append(nm)
        if vtype == 'toggle':
            dv = bool(vd.get('value', False))
            if nm not in vars_d or not isinstance(vars_d.get(nm), bool):
                vars_d[nm] = dv
            meta_d[nm] = {'type':'toggle'}
        else:
            try:
                dv = float(vd.get('value', 0.0) or 0.0)
            except Exception:
                dv = 0.0
            try:
                mn = float(vd.get('min', -1e9))
            except Exception:
                mn = -1e9
            try:
                mx = float(vd.get('max', 1e9))
            except Exception:
                mx = 1e9
            if mx < mn:
                mn, mx = mx, mn
            if nm not in vars_d or isinstance(vars_d.get(nm), bool):
                vars_d[nm] = dv
            # clamp
            try:
                vars_d[nm] = float(clamp(float(vars_d.get(nm, dv) or 0.0), mn, mx))
            except Exception:
                vars_d[nm] = dv
            meta_d[nm] = {'type':'number','min':mn,'max':mx}
    # prune removed vars
    for k in list(vars_d.keys()):
        if k not in meta_d:
            vars_d.pop(k, None)
    state['vars'] = vars_d
    state['_vars_meta'] = meta_d
    state['_vars_sig'] = sig

def _get_number_var(state: EffectState, name: str, default: float = 0.0) -> float:
    if not isinstance(state, dict):
        return float(default)
    vd = state.get('vars')
    if not isinstance(vd, dict):
        return float(default)
    try:
        v = vd.get(str(name))
        if isinstance(v, bool) or v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _state_for_layer(params: dict, fallback_state: dict, layer_index: int) -> dict:
    """Return layer state dict for layer_index if available, else fallback_state."""
    try:
        li = int(layer_index)
    except Exception:
        li = -1
    if li < 0:
        return fallback_state
    try:
        all_states = params.get('_all_states') if isinstance(params, dict) else None
        if isinstance(all_states, list) and 0 <= li < len(all_states) and isinstance(all_states[li], dict):
            return all_states[li]
    except Exception:
        pass
    return fallback_state

def _bound_multiplier(params: dict, fallback_state: dict, var_name: str, layer_index: int) -> float:
    try:
        vn = str(var_name or '').strip()
    except Exception:
        vn = ''
    if not vn:
        return 1.0
    st = _state_for_layer(params, fallback_state, layer_index)
    try:
        return float(_get_number_var(st, vn, default=1.0) or 1.0)
    except Exception:
        return 1.0

def _parse_layer_varref(ref: str):
    """Accept 'L2.varname' and return (layer_index or None, varname)."""
    try:
        s = str(ref or '').strip()
    except Exception:
        return None, ''
    if not s:
        return None, ''
    if (s[0] in ('L','l')) and '.' in s:
        head, rest = s.split('.', 1)
        head = head.strip()
        rest = rest.strip()
        try:
            li = int(head[1:])
            return li, rest
        except Exception:
            return None, s
    return None, s

def _get_number_var_ref(params: dict, fallback_state: dict, ref: str, default: float = 0.0) -> float:
    li, vn = _parse_layer_varref(ref)
    if li is None:
        return _get_number_var(fallback_state, vn, default)
    st = _state_for_layer(params, fallback_state, int(li))
    return _get_number_var(st, vn, default)

def _get_toggle_var_ref(params: dict, fallback_state: dict, ref: str, default: bool = False) -> bool:
    li, vn = _parse_layer_varref(ref)
    if li is None:
        try:
            return bool((fallback_state.get('vars') or {}).get(vn, default))
        except Exception:
            return bool(default)
    st = _state_for_layer(params, fallback_state, int(li))
    try:
        return bool((st.get('vars') or {}).get(vn, default))
    except Exception:
        return bool(default)

def _set_number_var(state: EffectState, name: str, value: float) -> None:
    if not isinstance(state, dict):
        return
    vd = state.get('vars')
    meta = state.get('_vars_meta')
    if not isinstance(vd, dict) or not isinstance(meta, dict):
        return
    nm = str(name)
    m = meta.get(nm) or {}
    if str(m.get('type')) != 'number':
        return
    mn = float(m.get('min', -1e9) or -1e9)
    mx = float(m.get('max', 1e9) or 1e9)
    try:
        vd[nm] = float(clamp(float(value), mn, mx))
    except Exception:
        pass

def _set_toggle_var(state: EffectState, name: str, value: bool) -> None:
    if not isinstance(state, dict):
        return
    vd = state.get('vars')
    meta = state.get('_vars_meta')
    if not isinstance(vd, dict) or not isinstance(meta, dict):
        return
    nm = str(name)
    m = meta.get(nm) or {}
    if str(m.get('type')) != 'toggle':
        return
    vd[nm] = bool(value)

def _apply_rules(state: EffectState, rules, dt: float, events: dict | None = None, params: dict | None = None) -> None:
    if not isinstance(state, dict):
        return
    if not isinstance(rules, list) or not rules:
        return
    if not isinstance(events, dict):
        events = {}

    # Per-rule timers live in state so timer triggers are stable across ticks.
    if not isinstance(state.get('_rule_timers'), dict):
        state['_rule_timers'] = {}
    timers: dict = state['_rule_timers']

    # : per-rule cooldowns
    if not isinstance(state.get('_rule_last_fire'), dict):
        state['_rule_last_fire'] = {}
    last_fire: dict = state['_rule_last_fire']
    now_t = float(state.get('_rule_time', 0.0) or 0.0)


    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            continue
        if not bool(r.get('enabled', True)):
            continue

        # -------- Trigger gate (): decide whether this rule should even be evaluated this tick.
        trig = r.get('trigger') if isinstance(r.get('trigger'), dict) else {}
        ttype = str(trig.get('type', 'every_tick') or 'every_tick').lower().strip()
        uid = str(r.get('uid') or trig.get('uid') or f"idx_{i}")

        # : cross-layer triggers (read trigger vars/events from another layer)
        tstate = state
        tevents = events
        tli = -1
        try:
            tli = trig.get('layer', -1)
            tli = int(tli) if tli is not None else -1
            if tli >= 0 and isinstance(params, dict):
                all_states = params.get('_all_states')
                if isinstance(all_states, list) and tli < len(all_states) and isinstance(all_states[tli], dict):
                    tstate = all_states[tli]
                    tevents = tstate.get('_events') if isinstance(tstate.get('_events'), dict) else tevents
        except Exception:
            tstate = state
            tevents = events


        # : Variable-change triggers (state-driven, no timers needed)
        if ttype in ('on_var_change','var_change','var_changed'):
            vname = str(trig.get('var','') or '').strip()
            if not vname:
                continue
            store = state.setdefault('_rule_prev_vars', {})
            prev = store.get((uid, vname), None)
            cur = (tstate.get('vars') or {}).get(vname, None) if isinstance(state, dict) else None
            store[(uid, vname)] = cur
            if prev is None or cur == prev:
                continue
        
        if ttype in ('on_var_cross','var_cross','cross'):
            vname = str(trig.get('var','') or '').strip()
            op = str(trig.get('op','>') or '>').strip()
            try:
                thresh = float(trig.get('value', 0.0) or 0.0)
            except Exception:
                thresh = 0.0
            if not vname:
                continue
            store = state.setdefault('_rule_prev_vars', {})
            prev = store.get((uid, vname), None)
            try:
                cur = float((tstate.get('vars') or {}).get(vname, 0.0) or 0.0)
            except Exception:
                cur = 0.0
            store[(uid, vname)] = cur
            if prev is None:
                continue
            try:
                prevf = float(prev)
            except Exception:
                prevf = cur
            def _cmp(x):
                if op == '>': return x > thresh
                if op == '<': return x < thresh
                if op == '>=': return x >= thresh
                if op == '<=': return x <= thresh
                if op == '==': return x == thresh
                return x > thresh
            if (not _cmp(prevf)) and _cmp(cur):
                pass
            else:
                continue
        
        # : Spawn/Despawn triggers (event-driven)
        if ttype in ('on_spawn','spawn'):
            try:
                n = int((tevents or {}).get('spawn', 0) or 0)
            except Exception:
                n = 0
            if n <= 0:
                continue
        
        if ttype in ('on_despawn','despawn'):
            try:
                n = int((tevents or {}).get('despawn', 0) or 0)
            except Exception:
                n = 0
            if n <= 0:
                continue
        
        if ttype in ('on_target_hit', 'target_hit', 'on_hit'):
            if int(tevents.get('target_hit', 0) or 0) <= 0:
                continue
        if ttype in ('on_wall_hit','wall_hit'):
            if int(tevents.get('wall_hit', 0) or 0) <= 0:
                continue
        if ttype in ('on_wrap','wrap'):
            if int(tevents.get('wrap', 0) or 0) <= 0:
                continue
        if ttype in ('on_bounds_exit','bounds_exit','out_of_bounds'):
            if int(tevents.get('bounds_exit', 0) or 0) <= 0:
                continue

        if ttype in ('on_pp_collision','pp_collision','on_particle_collision','particle_collision'):
            if int(tevents.get('pp_collision', 0) or 0) <= 0:
                continue
        if ttype in ('on_pp_near','pp_near','on_particle_near','particle_near'):
            if int(tevents.get('pp_near', 0) or 0) <= 0:
                continue

        elif ttype in ('timer', 'interval'):
            try:
                interval = float(trig.get('interval', 1.0) or 1.0)
            except Exception:
                interval = 1.0
            if interval <= 0.0:
                interval = 0.0
            key = f"t::{uid}"
            timers[key] = float(timers.get(key, 0.0) or 0.0) + float(dt)
            if interval > 0.0 and float(timers.get(key, 0.0)) < interval:
                continue
            # Fire and reset
            timers[key] = 0.0
        else:
            # every_tick (default)
            pass

        cond = r.get('cond') if isinstance(r.get('cond'), dict) else {}
        act = r.get('act') if isinstance(r.get('act'), dict) else {}

        # Evaluate condition
        ok = True
        try:
            vname = str(cond.get('var','') or '')
            op = str(cond.get('op','') or '').lower().strip()
            # : cross-layer condition reading
            cstate = state
            try:
                cli = cond.get('layer', cond.get('var_layer', -1))
                cli = int(cli) if cli is not None else -1
                all_states = params.get('_all_states') if isinstance(params, dict) else None
                if isinstance(all_states, list) and cli >= 0 and cli < len(all_states) and isinstance(all_states[cli], dict):
                    cstate = all_states[cli]
            except Exception:
                cstate = state

            # If condition var missing, treat as false for non-empty op
            if vname and op:
                meta = (cstate.get('_vars_meta') or {}).get(vname) if isinstance(cstate.get('_vars_meta'), dict) else None
                vtype = str((meta or {}).get('type','number'))
                if vtype == 'toggle':
                    cur = bool((cstate.get('vars') or {}).get(vname, False))
                    want = bool(cond.get('value', True))
                    if op in ('true','is_true','=='):
                        ok = (cur is True) if (op != '==') else (cur == want)
                    elif op in ('false','is_false'):
                        ok = (cur is False)
                    else:
                        ok = (cur == want)
                else:
                    cur = _get_number_var(cstate, vname, 0.0)
                    try:
                        rhs = float(cond.get('value', 0.0) or 0.0)
                    except Exception:
                        rhs = 0.0
                    if op == '>':
                        ok = cur > rhs
                    elif op == '<':
                        ok = cur < rhs
                    elif op in ('>=','=>'):
                        ok = cur >= rhs
                    elif op in ('<=','=<'):
                        ok = cur <= rhs
                    elif op in ('==','eq'):
                        ok = abs(cur - rhs) <= 1e-9
                    else:
                        ok = True
        except Exception:
            ok = True
        if not ok:
            continue
        # Cooldown gate (seconds). 0 = unlimited.
        cd = 0.0
        try:
            cd = float(r.get('cooldown', 0.0) or 0.0)

            # Record cooldown timestamp if enabled
            try:
                if cd > 0.0 and did_any:
                    last_fire[uid] = float(now_t)
            except Exception:
                pass

        except Exception:
            cd = 0.0
        if cd > 0.0:
            last = float(last_fire.get(uid, -1e30) or -1e30)
            if (now_t - last) < cd:
                continue

        # Apply action
        try:
            kind = str(act.get('kind','var') or 'var').lower().strip()
            # : allow actions to target other layers/effects
            tgt_state = state
            try:
                tli = act.get('target_layer', -1)
                tli = int(tli) if tli is not None else -1
                all_states = params.get('_all_states') if isinstance(params, dict) else None
                if isinstance(all_states, list) and tli >= 0 and tli < len(all_states):
                    if isinstance(all_states[tli], dict):
                        tgt_state = all_states[tli]
            except Exception:
                tgt_state = state

            did_any = True
            did_force = False
            did_emitter = False

            # --- Emitter actions (spawn/burst + spawn_rate) ---
            if kind in ('emit','emitter','spawn'):
                did_emitter = True
                aop = str(act.get('op','set') or 'set').lower().strip()
                raw_key = str(act.get('var','') or '').strip().lower()
                # Allow targeting a specific emitter via 'emitter_index' or key prefix: 'e0|burst' / '0|burst'
                eidx = 0
                key = raw_key
                try:
                    if act.get('emitter_index') is not None:
                        eidx = int(act.get('emitter_index') or 0)
                except Exception:
                    eidx = 0
                if '|' in raw_key:
                    try:
                        left, right = raw_key.split('|', 1)
                        left = left.strip()
                        right = right.strip()
                        if left.startswith('e'):
                            left = left[1:]
                        eidx = int(left)
                        key = right
                    except Exception:
                        key = raw_key.split('|',1)[-1].strip()
                        eidx = 0
                if eidx < 0:
                    eidx = 0
            
                # Ensure emitters list exists for multi-emitter control; emitter 0 mirrors legacy keys.
                emitters = None
                if isinstance(params, dict):
                    emitters = params.get('emitters')
                    if not isinstance(emitters, list):
                        emitters = None
                    if emitters is None:
                        params['emitters'] = []
                        emitters = params['emitters']
                    # grow list if needed
                    while len(emitters) <= eidx:
                        emitters.append({'enabled': True, 'spawn_rate': 0.0, 'target_kind': '', 'target_id': ''})
            
                # key can be: 'spawn_rate'/'rate', 'burst', 'enabled'
                if key in ('burst','spawn_burst'):
                    # value interpreted as count
                    try:
                        n = int(round(float(act.get('value', 1) or 1)))
                    except Exception:
                        n = 1
                    n = max(0, min(500, n))
                    if n > 0 and isinstance(tgt_state, dict):
                        bkey = '_burst' if eidx == 0 else f'_burst_e{eidx}'
                        try:
                            tgt_state[bkey] = int(tgt_state.get(bkey, 0) or 0) + int(n)
                        except Exception:
                            tgt_state[bkey] = int(n)
                elif key in ('enabled','on','active'):
                    if emitters is not None and 0 <= eidx < len(emitters) and isinstance(emitters[eidx], dict):
                        if aop == 'toggle':
                            emitters[eidx]['enabled'] = not bool(emitters[eidx].get('enabled', True))
                        elif aop in ('set_true','true','on'):
                            emitters[eidx]['enabled'] = True
                        elif aop in ('set_false','false','off'):
                            emitters[eidx]['enabled'] = False
                        else:
                            emitters[eidx]['enabled'] = bool(act.get('value', True))
                elif key in ('target','target_id','target_kind'):
                    # Set per-emitter spawn target. Value format: 'group:<id>' or 'zone:<id>'
                    if emitters is not None and 0 <= eidx < len(emitters) and isinstance(emitters[eidx], dict):
                        raw = act.get('value', '')
                        s = str(raw or '').strip()
                        kind2 = ''
                        tid2 = ''
                        if ':' in s:
                            kind2, tid2 = s.split(':', 1)
                            kind2 = kind2.strip().lower()
                            tid2 = tid2.strip()
                        else:
                            # if provided separately
                            if key == 'target_kind':
                                kind2 = s.strip().lower()
                                tid2 = str((emitters[eidx] or {}).get('target_id','') or '').strip()
                            elif key == 'target_id':
                                tid2 = s.strip()
                                kind2 = str((emitters[eidx] or {}).get('target_kind','') or '').strip().lower()
                        if kind2 in ('group','zone') and tid2:
                            emitters[eidx]['target_kind'] = kind2
                            emitters[eidx]['target_id'] = tid2
                        elif s.lower() in ('clear','none','off',''):
                            emitters[eidx].pop('target_kind', None)
                            emitters[eidx].pop('target_id', None)
                else:
                    # numeric emitter params live in emitters list (preferred) or legacy params dict
                    if key in ('spawn_rate','rate'):
                        try:
                            val = float(act.get('value', 0.0) or 0.0)
                        except Exception:
                            val = 0.0
                        if val < 0.0:
                            val = 0.0
                        if emitters is not None and 0 <= eidx < len(emitters) and isinstance(emitters[eidx], dict):
                            cur = float(emitters[eidx].get('spawn_rate', 0.0) or 0.0)
                            if aop == 'set':
                                emitters[eidx]['spawn_rate'] = float(val)
                            elif aop in ('inc','add','+'):
                                emitters[eidx]['spawn_rate'] = float(cur + float(val))
                            elif aop in ('dec','sub','-'):
                                emitters[eidx]['spawn_rate'] = float(cur - float(val))
                            if float(emitters[eidx].get('spawn_rate', 0.0) or 0.0) < 0.0:
                                emitters[eidx]['spawn_rate'] = 0.0
                        else:
                            # legacy fallback
                            if isinstance(params, dict):
                                cur = float(params.get('spawn_rate', 0.0) or 0.0)
                                if aop == 'set':
                                    params['spawn_rate'] = float(val)
                                elif aop in ('inc','add','+'):
                                    params['spawn_rate'] = float(cur + float(val))
                                elif aop in ('dec','sub','-'):
                                    params['spawn_rate'] = float(cur - float(val))
                                if float(params.get('spawn_rate', 0.0) or 0.0) < 0.0:
                                    params['spawn_rate'] = 0.0
            # --- Force actions (: cross-layer + state-owned forces) ---
            if kind in ('force','forces'):
                did_force = True
                # Target layer override (supports act['layer'] or var prefix 'L2.')
                raw_key = str(act.get('var','') or '').strip()
                li_from_key, key2 = _parse_layer_prefix(raw_key)
                tli = -1
                try:
                    if act.get('layer') is not None:
                        tli = int(act.get('layer') or -1)
                except Exception:
                    tli = -1
                if tli < 0 and li_from_key is not None:
                    tli = int(li_from_key)
                if not key2:
                    key2 = raw_key
                # Resolve target state
                fstate = state
                if tli >= 0 and isinstance(params, dict):
                    try:
                        all_states = params.get('_all_states')
                        if isinstance(all_states, list) and 0 <= tli < len(all_states) and isinstance(all_states[tli], dict):
                            fstate = all_states[tli]
                    except Exception:
                        fstate = state
                # Ensure forces live in state (runtime truth); seed from params['forces'] on first use (only for same layer).
                if isinstance(fstate, dict) and not isinstance(fstate.get('_forces'), list):
                    try:
                        src_forces = params.get('forces') if (fstate is state and isinstance(params, dict)) else None
                        fstate['_forces'] = copy.deepcopy(src_forces) if isinstance(src_forces, list) else []
                    except Exception:
                        fstate['_forces'] = []
                forces = fstate.get('_forces') if isinstance(fstate, dict) else None
                if isinstance(forces, list):
                    # key format: 'f0|field' or '0|field'
                    try:
                        sidx, field = str(key2).split('|', 1)
                        sidx = str(sidx).strip().lower()
                        if sidx.startswith('f'):
                            sidx = sidx[1:]
                        fi = int(sidx)
                        field = str(field or '').strip().lower()
                    except Exception:
                        fi = -1
                        field = ''
                    if 0 <= fi < len(forces) and isinstance(forces[fi], dict) and field:
                        f = forces[fi]
                        aop = str(act.get('op','set') or 'set').lower().strip()
                        if field == 'enabled':
                            if aop == 'toggle':
                                f['enabled'] = not bool(f.get('enabled', True))
                            elif aop in ('set_false','false','off'):
                                f['enabled'] = False
                            elif aop in ('set_true','true','on'):
                                f['enabled'] = True
                            else:
                                f['enabled'] = bool(act.get('value', True))
                        else:
                            try:
                                curv = float(f.get(field, 0.0) or 0.0)
                            except Exception:
                                curv = 0.0
                            vsrc = str(act.get('value_source','const') or 'const').lower().strip()
                            if vsrc in ('event','events','event_count'):
                                ek = str(act.get('event_key','collision') or 'collision').lower().strip()
                                try: factor = float(act.get('factor', 1.0) or 1.0)
                                except Exception: factor = 1.0
                                try: val = float((tevents or {}).get(ek, 0) or 0.0) * float(factor)
                                except Exception: val = 0.0
                            else:
                                try: val = float(act.get('value', 0.0) or 0.0)
                                except Exception: val = 0.0
                            per_sec = bool(act.get('per_second', True))
                            dv = val * float(dt) if per_sec and aop in ('inc','dec','add','sub','+') else val
                            if aop == 'set':
                                f[field] = float(val)
                            elif aop in ('inc','add','+'):
                                f[field] = float(curv + dv)
                            elif aop in ('dec','sub','-'):
                                f[field] = float(curv - dv)
                # done
                # done

            # --- Variable actions (default) ---
            if (not did_force) and (not did_emitter):
                tgt = str(act.get('var','') or '')
                aop = str(act.get('op','set') or 'set').lower().strip()
                meta = (tgt_state.get('_vars_meta') or {}).get(tgt) if isinstance(tgt_state.get('_vars_meta'), dict) else None
                vtype = str((meta or {}).get('type','number'))
                if vtype == 'toggle':
                    if aop in ('set','set_true','true'):
                        _set_toggle_var(tgt_state, tgt, True if aop!='set' else bool(act.get('value', True)))
                    elif aop in ('set_false','false'):
                        _set_toggle_var(tgt_state, tgt, False)
                    elif aop in ('toggle',):
                        cur = bool((tgt_state.get('vars') or {}).get(tgt, False))
                        _set_toggle_var(tgt_state, tgt, not cur)
                else:
                    cur = _get_number_var(tgt_state, tgt, 0.0)
                    try:
                        val = float(act.get('value', 0.0) or 0.0)
                    except Exception:
                        val = 0.0
                    per_sec = bool(act.get('per_second', True))
                    dv = val * float(dt) if per_sec and aop in ('inc','dec','add','sub') else val
                    if aop in ('set',):
                        _set_number_var(tgt_state, tgt, val)
                    elif aop in ('inc','add','+'):
                        _set_number_var(tgt_state, tgt, cur + dv)
                    elif aop in ('dec','sub','-'):
                        _set_number_var(tgt_state, tgt, cur - dv)
        except Exception:
            pass
USES = [
    "color",
    "brightness",
    "speed",        # sim speed multiplier
    "speed_bind_var",  # optional number variable to multiply speed
    "enemy_count",  # number of particles
    "enemy_count_bind_var",  # optional number variable to multiply enemy_count
    "max_entities",  # cap for continuous spawning
    "max_entities_bind_var",  # optional number variable to multiply max_entities
    "spawn_rate",  # particles per second (0 = legacy count mode)
    "spawn_rate_bind_var",  # optional number variable to multiply spawn_rate
    "lifetime",  # seconds (0 = immortal)
    "lifetime_bind_var",  # optional number variable to multiply lifetime
    "gravity",      # force strength magnitude
    "gravity_bind_var",  # optional number variable to multiply gravity
    "friction",     # velocity damping
    "friction_bind_var",  # optional number variable to multiply friction
    "wrap_edges",   # wrap or bounce
    "edge_mode",
    "force_mode",   # attract or repel
    "force_source", # center or fixed point
    "source_x",     # fixed source X (cells)
    "source_y",     # fixed source Y (cells)
    "pairwise_repel",
    "repel_strength",
    "repel_strength_bind_var",  # optional number variable to multiply separation strength
    "repel_range",

    # Rules MVP → expanded into beginner-friendly "Target Dots" list.
    # Back-compat single-dot fields remain, but the preferred interface is:
    # params["targets"] = [{enabled, color, mode, interval}, ...]
    "dot_enabled",
    "dot_color",
    "dot_spawn_mode",      # on_hit or timer
    "dot_spawn_interval",  # seconds
    "targets",
    "pp_mode",
    "pp_radius",
    "pp_max_pairs",
    "rng_seed",
    "fixed_step_hz",
    "max_substeps",
]


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _apply_brightness(rgb: RGB, br: float) -> RGB:
    try:
        br = float(br)
    except Exception:
        br = 1.0
    br = _clamp01(br)
    r, g, b = rgb
    return (int(r * br) & 255, int(g * br) & 255, int(b * br) & 255)


def _spawn_particle(rng: DeterministicRNG, w: int, h: int, mask: list[int] | None = None) -> dict:
    # If a target mask is provided, spawn inside it (Zones/Groups become first-class spawn areas).
    idx = None
    if mask:
        try:
            idx = int(rng.choice(list(mask)))
        except Exception:
            idx = None
    if idx is not None and w > 0 and h > 0:
        x = float(idx % int(w))
        y = float(idx // int(w))
    else:
        x = rng.uniform(0.0, float(w - 1)) if w > 1 else 0.0
        y = rng.uniform(0.0, float(h - 1)) if h > 1 else 0.0
    vx = rng.uniform(-0.5, 0.5)
    vy = rng.uniform(-0.5, 0.5)
    return {"x": x, "y": y, "vx": vx, "vy": vy, "age": 0.0}

def _ensure_state(state: EffectState, *, w: int, h: int) -> None:
    """Ensure minimal runtime state exists (does NOT hard-reset particles)."""
    if not isinstance(state, dict):
        return
    if "rng_seed" not in state:
        state["rng_seed"] = 1337
    if "rng" not in state or not isinstance(state.get("rng"), DeterministicRNG):
        state["rng"] = DeterministicRNG(int(state.get("rng_seed", 1337)))

    # Layout cache
    state["w"] = int(w)
    state["h"] = int(h)

    # particles list exists
    parts = state.get("p")
    if not isinstance(parts, list):
        state["p"] = []

    # Spawn accumulator for continuous spawning
    if "spawn_accum" not in state:
        state["spawn_accum"] = 0.0

    # Rules: list of target dots + a score counter
    if "targets" not in state or not isinstance(state.get("targets"), list):
        state["targets"] = []  # each: {x,y,timer}
    if "score" not in state:
        state["score"] = 0


def _get_targets_from_params(params: dict) -> list[dict]:
    """Normalize targets list from params (with back-compat for dot_*)."""
    targets = params.get("targets")
    if isinstance(targets, list) and targets:
        out = []
        for t in targets:
            if not isinstance(t, dict):
                continue
            out.append({
                "enabled": bool(t.get("enabled", True)),
                "color": t.get("color", (0, 255, 0)),
                "mode": str(t.get("mode", t.get("spawn_mode", "on_hit")) or "on_hit").lower().strip(),
                "interval": float(t.get("interval", t.get("spawn_interval", 1.0)) or 1.0),
            })
        return out

    # Back-compat single dot
    if bool(params.get("dot_enabled", False)):
        return [{
            "enabled": True,
            "color": params.get("dot_color", (0, 255, 0)),
            "mode": str(params.get("dot_spawn_mode", "on_hit") or "on_hit").lower().strip(),
            "interval": float(params.get("dot_spawn_interval", 1.0) or 1.0),
        }]
    return []


def _spawn_dot(*, state: EffectState, w: int, h: int, exclude_cells: set[int]) -> None:
    """Pick a new dot position within bounds, avoiding exclude_cells."""
    try:
        rng: DeterministicRNG = state["rng"]
    except Exception:
        state["rng"] = DeterministicRNG(int(state.get("rng_seed", 1337)))
        rng = state["rng"]

    if w <= 0 or h <= 0:
        state["dot"] = {"x": None, "y": None}
        return

    # Build a list of available cells if the playfield isn't huge.
    total = int(w) * int(h)
    if total <= 1:
        state["dot"] = {"x": 0, "y": 0}
        return

    # If exclusion is small, attempt random picks with a cap.
    max_tries = 300
    for _ in range(max_tries):
        xi = int(rng.randint(0, max(0, w - 1)))
        yi = int(rng.randint(0, max(0, h - 1)))
        idx = yi * w + xi
        if idx not in exclude_cells:
            state["dot"] = {"x": xi, "y": yi}
            return

    # Fallback: pick the first free cell.
    for idx in range(total):
        if idx not in exclude_cells:
            xi = idx % w
            yi = idx // w
            state["dot"] = {"x": xi, "y": yi}
            return

    state["dot"] = {"x": None, "y": None}


def _update(*, state: EffectState, params: dict, dt: float, t: float, audio: dict | None = None) -> None:
    # Determine bounds from cached layout
    try:
        w = int(state.get("w", 60))
        h = int(state.get("h", 1))
    except Exception:
        w, h = 60, 1

    # : Deterministic stepping (fixed dt) to keep simulation stable and reproducible.
    try:
        step_hz = int(params.get('fixed_step_hz', 60) or 60)
    except Exception:
        step_hz = 60
    if step_hz < 10:
        step_hz = 10
    if step_hz > 240:
        step_hz = 240
    fixed_dt = 1.0 / float(step_hz)
    try:
        max_sub = int(params.get('max_substeps', 5) or 5)
    except Exception:
        max_sub = 5
    if max_sub < 1:
        max_sub = 1
    if max_sub > 50:
        max_sub = 50
    # Clamp big frame times; we intentionally run at fixed_dt for determinism.
    try:
        dt_in = float(dt or 0.0)
    except Exception:
        dt_in = 0.0
    if dt_in < 0.0:
        dt_in = 0.0
    if dt_in > fixed_dt * float(max_sub):
        dt_in = fixed_dt * float(max_sub)
    dt = fixed_dt


    # ---- /17: Variables + Rules ----
    # Initialize an event bag early so triggers are stable, and sync variables
    # before any variable-bound params are computed.
    if isinstance(state, dict):
        state['_events'] = {'target_hit': 0, 'collision': 0, 'enter': 0, 'exit': 0, 'spawn': 0, 'despawn': 0}
    _sync_variables(state, params.get("_vars_def"))
    # Legacy: enemy_count is still the base "initial/target" count.
    base_count = int(params.get("enemy_count", 24) or 24)
    cv = str(params.get("enemy_count_bind_var", "") or "").strip()
    cv_li = int(params.get("enemy_count_bind_layer", -1) or -1)
    if cv:
        try:
            base_count = int(round(float(base_count) * float(_get_number_var_ref(params, state, cv, 1.0))))
        except Exception:
            pass
    base_count = max(0, min(200, base_count))

    # : Continuous spawning (spawn_rate) + max_entities cap, both optionally bindable.
    max_entities = int(params.get("max_entities", base_count) or base_count)
    mv = str(params.get("max_entities_bind_var", "") or "").strip()
    mv_li = int(params.get("max_entities_bind_layer", -1) or -1)
    if mv:
        try:
            max_entities = int(round(float(max_entities) * float(_get_number_var_ref(params, state, mv, 1.0))))
        except Exception:
            pass
    max_entities = max(0, min(200, max_entities))

    spawn_rate = float(params.get("spawn_rate", 0.0) or 0.0)
    sv = str(params.get("spawn_rate_bind_var", "") or "").strip()
    sv_li = int(params.get("spawn_rate_bind_layer", -1) or -1)
    if sv:
        try:
            spawn_rate = float(spawn_rate) * float(_get_number_var_ref(params, state, sv, 1.0))
        except Exception:
            pass
    if spawn_rate < 0.0:
        spawn_rate = 0.0

    try:
        state['rng_seed'] = int(params.get('rng_seed', state.get('rng_seed', 1337)) or 1337)
    except Exception:
        state['rng_seed'] = int(state.get('rng_seed', 1337) or 1337)
    try:
        _ = state.get('rng')
    except Exception:
        state['rng'] = DeterministicRNG(int(state.get('rng_seed', 1337)))

    _ensure_state(state, w=w, h=h)
    parts = state.get("p") or []

    # Ensure the effect is visibly active by default.
    # Many historical projects relied on external spawn triggers; for a clean
    # single-layer preview (and diagnostics), seed an initial particle set if
    # none exist yet.
    if isinstance(parts, list) and len(parts) == 0 and base_count > 0:
        try:
            rng = state.get("rng")
        except Exception:
            rng = None
        try:
            seed_n = int(max(6, min(base_count, 48)))
        except Exception:
            seed_n = 12
        # spawn roughly across the playfield
        for _i in range(seed_n):
            try:
                # DeterministicRNG provides .u01(); fall back to hash if needed.
                u = float(rng.u01()) if rng is not None and hasattr(rng, 'u01') else 0.5
                v = float(rng.u01()) if rng is not None and hasattr(rng, 'u01') else 0.5
            except Exception:
                u, v = 0.5, 0.5
            x = u * float(max(1, w - 1))
            y = v * float(max(1, h - 1))
            parts.append({'x': x, 'y': y, 'vx': 0.0, 'vy': 0.0})
        state['p'] = parts

    # Target selection (may be empty for 'all')
    target_kind = str(params.get('target_kind', params.get('spawn_target_kind','all')) or 'all').lower().strip()
    target_id = str(params.get('target_id', params.get('spawn_target_id','')) or '').strip()
    # : Use layer target mask (Zones/Groups) as spawn area when present
    try:
        # : resolve spawn mask via project registry when available
        spawn_mask = None
        try:
            app = state.get('_app') if isinstance(state, dict) else None
            reg = getattr(app, 'zones_registry', None) if app else None
            if reg and target_kind in ('zone','group') and target_id:
                spawn_mask = set(reg.resolve_indices(target_kind, target_id))
        except Exception:
            spawn_mask = None
        if spawn_mask is None:
            spawn_mask = _resolve_target_mask(target_kind, target_id, w, h)
    except Exception:
        spawn_mask = []


    # : per-tick events for rule triggers
    try:
        state['_events'] = {'spawn': 0, 'despawn': 0, 'collision': 0, 'enter': 0, 'exit': 0, 'target_hit': 0}
    except Exception:
        pass


    # : Detect significant param changes and re-seed so changes are immediately visible.
    try:
        sig = (
            float(spawn_rate),
            int(max_entities),
            int(base_count),
            float(lifetime),
        )
        if state.get("_sig") != sig:
            state["_sig"] = sig
            state["_seeded_particles"] = False
            state["spawn_accum"] = 0.0
    except Exception:
        pass

    rng: DeterministicRNG = state.get("rng")  # type: ignore


    # : Particle lifetime (seconds). 0 means immortal.
    lifetime = float(params.get("lifetime", 0.0) or 0.0)
    lv = str(params.get("lifetime_bind_var", "") or "").strip()
    lv_li = int(params.get("lifetime_bind_layer", -1) or -1)
    if lv:
        try:
            lifetime = float(lifetime) * float(_get_number_var_ref(params, state, lv, 1.0))
        except Exception:
            pass
    if lifetime < 0.0:
        lifetime = 0.0


    # Seed particles once so demo is immediately visible.
    if isinstance(state, dict) and not state.get("_seeded_particles"):
        seed = base_count
        if spawn_rate > 0.0:
            seed = min(base_count, max_entities)
        try:
            for _ in range(int(seed)):
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try:
                    state['_events']['spawn'] += 1
                except Exception:
                    pass
        except Exception:
            pass
        state["_seeded_particles"] = True


    # : Multi-emitter spawning (supports multiple independent emitters per effect).
    emitters = None
    try:
        emitters = params.get('emitters') if isinstance(params, dict) else None
    except Exception:
        emitters = None
    if not isinstance(emitters, list) or len(emitters) == 0:
        # Back-compat: single implicit emitter using legacy spawn_rate + _burst.
        emitters = [{'enabled': True, 'spawn_rate': float(spawn_rate), 'burst_key': '_burst', 'mask': spawn_mask}]
    else:
        # Ensure each emitter has minimal fields; emitter 0 may mirror legacy.
        for ei, em in enumerate(emitters):
            if not isinstance(em, dict):
                emitters[ei] = {'enabled': True, 'spawn_rate': 0.0}
            if 'enabled' not in emitters[ei]:
                emitters[ei]['enabled'] = True
            if 'spawn_rate' not in emitters[ei]:
                emitters[ei]['spawn_rate'] = 0.0
    
    # Seed particles once so demo is immediately visible (uses emitter 0 config).
    if isinstance(state, dict) and not state.get('_seeded_particles'):
        seed = base_count
        try:
            e0_rate = float(emitters[0].get('spawn_rate', spawn_rate) or 0.0)
        except Exception:
            e0_rate = float(spawn_rate)
        if e0_rate > 0.0:
            seed = min(base_count, max_entities)
        try:
            e0_mask = emitters[0].get('mask', spawn_mask) if isinstance(emitters[0], dict) else spawn_mask
        except Exception:
            e0_mask = spawn_mask
        try:
            for _ in range(int(seed)):
                parts.append(_spawn_particle(rng, w, h, e0_mask))
                try: state['_events']['spawn'] += 1
                except Exception: pass
        except Exception:
            pass
        state['_seeded_particles'] = True
    
    # Apply per-emitter burst and continuous spawn. All emitters contribute into the same particle pool.
    for ei, em in enumerate(emitters):
        if not isinstance(em, dict):
            continue
        if not bool(em.get('enabled', True)):
            continue
        try:
            em_rate = float(em.get('spawn_rate', 0.0) or 0.0)
        except Exception:
            em_rate = 0.0
        if ei == 0 and (not isinstance(params.get('emitters'), list) or len(params.get('emitters') or []) == 0):
            # implicit emitter already copied legacy rate
            pass
        # choose spawn mask
        # choose spawn mask (per-emitter targets override layer target)
        em_mask = spawn_mask
        try:
            # explicit mask wins if provided
            if isinstance(em, dict) and em.get('mask') is not None:
                em_mask = em.get('mask')
            else:
                ek = str((em or {}).get('target_kind','') or '').strip().lower()
                eid = str((em or {}).get('target_id','') or '').strip()
                if ek in ('zone','group') and eid:
                    try:
                        app = state.get('_app') if isinstance(state, dict) else None
                        reg = getattr(app, 'zones_registry', None) if app else None
                        if reg:
                            em_mask = set(reg.resolve_indices(ek, eid))
                        else:
                            em_mask = _resolve_target_mask(ek, eid, w, h)
                    except Exception:
                        em_mask = _resolve_target_mask(ek, eid, w, h)
        except Exception:
            em_mask = spawn_mask
        bkey = str(em.get('burst_key','') or '').strip()
        if not bkey:
            bkey = '_burst' if ei == 0 else f'_burst_e{ei}'
        try:
            burst_n = int(state.get(bkey, 0) or 0) if isinstance(state, dict) else 0
        except Exception:
            burst_n = 0
        if burst_n > 0 and w > 0 and h > 0:
            try:
                cap = max_entities if max_entities > 0 else 200
                burst_n = min(burst_n, max(0, cap - len(parts)))
                for _ in range(int(burst_n)):
                    parts.append(_spawn_particle(rng, w, h, em_mask))
                    try: state['_events']['spawn'] += 1
                    except Exception: pass
            except Exception:
                pass
            try:
                state[bkey] = 0
            except Exception:
                pass
        # Continuous spawning: per-emitter accumulator
        if em_rate > 0.0:
            acc_key = f'spawn_accum_e{ei}'
            try:
                state[acc_key] = float(state.get(acc_key, 0.0) or 0.0) + float(em_rate) * float(dt)
            except Exception:
                state[acc_key] = 0.0
            try:
                while float(state.get(acc_key, 0.0)) >= 1.0 and len(parts) < max_entities:
                    parts.append(_spawn_particle(rng, w, h, em_mask))
                    try: state['_events']['spawn'] += 1
                    except Exception: pass
                    state[acc_key] = float(state.get(acc_key, 0.0)) - 1.0
            except Exception:
                pass
    
    # If NO emitter has continuous spawn, keep legacy soft-adjust to base_count (for backward projects).
    any_cont = False
    try:
        for em in emitters:
            if isinstance(em, dict) and bool(em.get('enabled', True)) and float(em.get('spawn_rate', 0.0) or 0.0) > 0.0:
                any_cont = True
                break
    except Exception:
        any_cont = False
    if not any_cont:
        target = base_count
        if len(parts) < target:
            add_n = min(target - len(parts), max(1, int(round(12 * float(dt)))))
            for _ in range(add_n):
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try: state['_events']['spawn'] += 1
                except Exception: pass
        elif len(parts) > target:
            rem_n = min(len(parts) - target, max(1, int(round(12 * float(dt)))))
            if rem_n > 0:
                del parts[-rem_n:]
                try: state['_events']['despawn'] += int(rem_n)
                except Exception: pass
    # Enforce cap if reduced
    if len(parts) > max_entities:
        del parts[max_entities:]
    # : Advance ages and prune expired particles (no hard reset).
    if lifetime > 0.0:
        try:
            for p in parts:
                try:
                    p["age"] = float(p.get("age", 0.0)) + float(dt)
                except Exception:
                    p["age"] = float(dt)
            # Keep only those not expired
            _prev_len = len(parts)
            parts[:] = [p for p in parts if float(p.get("age", 0.0)) <= float(lifetime)]
            try:
                state['_events']['despawn'] += max(0, int(_prev_len - len(parts)))
            except Exception:
                pass
        except Exception:
            pass
    else:
        # still maintain age for completeness
        try:
            for p in parts:
                if "age" in p:
                    p["age"] = float(p.get("age", 0.0)) + float(dt)
        except Exception:
            pass



    # : If continuous spawning is enabled and we're empty, spawn at least one immediately
    # so the user sees a response after changing settings.
    if spawn_rate > 0.0 and max_entities > 0 and len(parts) == 0:
        try:
            parts.append(_spawn_particle(rng, w, h, spawn_mask))
            try:
                state['_events']['spawn'] += 1
            except Exception:
                pass
        except Exception:
            pass



    # : Mirror resolved sim knobs into vars so the existing preview overlay shows them.
    # (Prefix with '_' so they're clearly debug-only.)
    try:
        vmap = state.get("vars")
        if isinstance(vmap, dict):
            vmap["_particles"] = float(len(parts))
            vmap["_spawn_rate"] = float(spawn_rate)
            vmap["_max_entities"] = float(max_entities)
            vmap["_lifetime"] = float(lifetime)
    except Exception:
        pass

    # Rules: normalize targets
    targets_cfg = _get_targets_from_params(params)

    # Maintain a simple occupied set (rounded particle cells)
    occupied: set[int] = set()
    if targets_cfg and w > 0 and h > 0:
        for p in parts:
            try:
                xi = int(round(float(p.get("x", 0.0))))
                yi = int(round(float(p.get("y", 0.0))))
            except Exception:
                continue
            if 0 <= xi < w and 0 <= yi < h:
                occupied.add(yi * w + xi)

    # : Collision zone/group support via injected _target_mask (from PreviewEngine)
    try:
        tmask = params.get('_target_mask')
        if isinstance(tmask, list) and tmask:
            tset = {int(x) for x in tmask if isinstance(x, int) or str(x).isdigit()}
            hit_n = 0
            try:
                hit_n = len(occupied.intersection(tset)) if occupied else 0
            except Exception:
                hit_n = 0
            if isinstance(state, dict):
                ev = state.get('_events')
                if isinstance(ev, dict):
                    ev['collision'] = int(hit_n)
                    # : enter/exit events (any-particle inside mask)
                    try:
                        inside_now = bool(hit_n and hit_n > 0)
                        prev_inside = bool(state.get('_prev_inside_mask', False) if isinstance(state, dict) else False)
                        state['_prev_inside_mask'] = inside_now
                        ev['enter'] = 1 if (inside_now and not prev_inside) else 0
                        ev['exit'] = 1 if ((not inside_now) and prev_inside) else 0
                    except Exception:
                        pass
                    ev['target_hit'] = int(ev.get('target_hit',0) or 0) + int(hit_n)
    except Exception:
        pass

    # Ensure state targets list matches config length
    st_targets = state.get("targets")
    if not isinstance(st_targets, list):
        st_targets = []
    # Resize state list
    if len(st_targets) != len(targets_cfg):
        st_targets = [{"x": None, "y": None, "timer": 0.0} for _ in range(len(targets_cfg))]
        state["targets"] = st_targets

    # Tick + spawn targets
    for i, cfg in enumerate(targets_cfg):
        if not bool(cfg.get("enabled", True)):
            continue
        try:
            st_targets[i]["timer"] = float(st_targets[i].get("timer", 0.0)) + float(dt)
        except Exception:
            st_targets[i]["timer"] = 0.0

        dx = st_targets[i].get("x"); dy = st_targets[i].get("y")
        missing = (dx is None) or (dy is None)
        mode = str(cfg.get("mode", "on_hit") or "on_hit").lower().strip()
        interval = float(cfg.get("interval", 1.0) or 1.0)
        if interval < 0.0:
            interval = 0.0
        if missing:
            _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
            # _spawn_dot writes state['dot'], so map it into this slot
            dot = state.get("dot") or {}
            st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
            st_targets[i]["timer"] = 0.0
        elif mode == "timer" and interval > 0.0 and float(st_targets[i].get("timer", 0.0)) >= interval:
            _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
            dot = state.get("dot") or {}
            st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
            st_targets[i]["timer"] = 0.0

    # (Rules run after the hit check below; trigger-based rules use state['_events']).

    spd = float(params.get("speed", 1.0) or 1.0)
    # : optional variable binding for speed
    svb = str(params.get("speed_bind_var", "") or "").strip()
    svb_li = int(params.get("speed_bind_layer", -1) or -1)
    if svb:
        try:
            spd *= float(_get_number_var_ref(params, state, svb, 1.0))
        except Exception:
            pass

    # ---- : Multiple forces ----
    # If params['forces'] exists, use it. Otherwise, fall back to legacy single-force params.
    forces = state.get('_forces') if isinstance(state.get('_forces'), list) else params.get("forces")
    if not isinstance(forces, list):
        forces = []
        forces.append({
            "kind": "point",
            "mode": str(params.get("force_mode", "attract") or "attract"),
            "strength": float(params.get("gravity", 6.0) or 6.0),
            "radius": 0.0,
            "source": str(params.get("force_source", "center") or "center"),
            "x": float(params.get("source_x", 0.0) or 0.0),
            "y": float(params.get("source_y", 0.0) or 0.0),
            "strength_var": str(params.get("gravity_bind_var", "") or "").strip(),
            "strength_layer": int(params.get("gravity_bind_layer", -1) or -1),
            "radius_var": "",
            "enabled_var": "",
        })
        if bool(params.get("pairwise_repel", False)):
            forces.append({
                "kind": "separation",
                "strength": float(params.get("repel_strength", 4.0) or 4.0),
                "range": float(params.get("repel_range", 6.0) or 6.0),
                "strength_var": str(params.get("repel_strength_bind_var", "") or "").strip(),
                "strength_layer": int(params.get("repel_strength_bind_layer", -1) or -1),
            })

    # Global sim knobs
    fr = float(params.get("friction", 0.0) or 0.0)
    # : optional variable binding for friction
    fvb = str(params.get("friction_bind_var", "") or "").strip()
    fvb_li = int(params.get("friction_bind_layer", -1) or -1)
    if fvb:
        try:
            fr *= float(_get_number_var_ref(params, state, fvb, 1.0))
        except Exception:
            pass
    fr = 0.0 if fr < 0.0 else (10.0 if fr > 10.0 else fr)
    wrap_edges = bool(params.get("wrap_edges", True))

    # Precompute layout center
    cx_center = (float(w - 1) / 2.0) if w > 1 else 0.0
    cy_center = (float(h - 1) / 2.0) if h > 1 else 0.0

    # Apply any separation forces first (pairwise)
    sep_forces = [f for f in forces if isinstance(f, dict) and str(f.get("kind","")) == "separation"]
    for sf in sep_forces:
        try:
            repel_k = float(sf.get("strength", 4.0) or 4.0) * float(spd)
        except Exception:
            repel_k = 0.0
        try:
            repel_range = float(sf.get("range", 6.0) or 6.0)
        except Exception:
            repel_range = 0.0
        if repel_range < 0.0:
            repel_range = 0.0

        rv = str(sf.get("range_var", "") or "").strip()
        if rv:
            try:
                repel_range *= float(_get_number_var_ref(params, state, rv, 1.0))
            except Exception:
                pass
        sv = str(sf.get("strength_var", "") or "").strip()

        if not bool(sf.get('enabled', True)):
            continue
        ev = str(sf.get("enabled_var", "") or "").strip()
        if ev:
            # Toggle variable gating this force
            try:
                if not _get_toggle_var_ref(params, state, ev, False):
                    continue
            except Exception:
                continue
        if sv:
            repel_k *= _get_number_var_ref(params, state, sv, 1.0)
        if repel_k <= 0.0 or repel_range <= 0.0 or len(parts) <= 1:
            continue
        rr2 = float(repel_range) * float(repel_range)
        max_pairs_n = 140
        parts_for_sep = parts if len(parts) <= max_pairs_n else parts[:max_pairs_n]
        for i in range(len(parts_for_sep) - 1):
            pi = parts_for_sep[i]
            xi = float(pi.get("x", 0.0)); yi = float(pi.get("y", 0.0))
            vxi = float(pi.get("vx", 0.0)); vyi = float(pi.get("vy", 0.0))
            for j in range(i + 1, len(parts_for_sep)):
                pj = parts_for_sep[j]
                xj = float(pj.get("x", 0.0)); yj = float(pj.get("y", 0.0))
                dx = xi - xj
                dy = yi - yj
                d2 = dx*dx + dy*dy
                if d2 < 1e-6 or d2 > rr2:
                    continue
                d = math.sqrt(d2)
                ux = dx / d
                uy = dy / d
                mag = (repel_k / d2)
                mag = clamp(mag, 0.0, 2.5)
                vxi += ux * mag
                vyi += uy * mag
                vxj = float(pj.get("vx", 0.0)) - ux * mag
                vyj = float(pj.get("vy", 0.0)) - uy * mag
                pj["vx"], pj["vy"] = vxj, vyj
            pi["vx"], pi["vy"] = vxi, vyi

    # Point forces (attract/repel) are applied per particle below.
    # Integrate (point forces)
    max_v = 25.0
    point_forces = [f for f in forces if isinstance(f, dict) and str(f.get('kind','point')) in ('point','force','attract','repel')]
    wall_hit_count = 0
    wrap_count = 0
    bounds_exit_count = 0
    killed = 0
    for p in parts:
        try:
            x = float(p.get('x', 0.0))
            y = float(p.get('y', 0.0))
            vx = float(p.get('vx', 0.0))
            vy = float(p.get('vy', 0.0))
        except Exception:
            continue

        for f in point_forces:
            try:
                mode = str(f.get('mode', 'attract') or 'attract').lower().strip()
                strength = float(f.get('strength', 0.0) or 0.0) * float(spd)
            except Exception:
                continue
            if mode in ('repel','away','push'):
                strength = -abs(strength)
            else:
                strength = abs(strength)
            sv = str(f.get('strength_var','') or '').strip()

            if not bool(f.get('enabled', True)):
                continue
            ev = str(f.get('enabled_var','') or '').strip()
            if ev:
                try:
                    if not _get_toggle_var_ref(params, state, ev, False):
                        continue
                except Exception:
                    continue
            if sv:
                strength *= _get_number_var_ref(params, state, sv, 1.0)

            src = str(f.get('source', 'center') or 'center').lower().strip()
            if src == 'fixed':
                try:
                    fx = float(f.get('x', cx_center) or cx_center)
                except Exception:
                    fx = cx_center
                try:
                    fy = float(f.get('y', cy_center) or cy_center)
                except Exception:
                    fy = cy_center
                fx = clamp(fx, 0.0, float(max(0, w - 1)))
                fy = clamp(fy, 0.0, float(max(0, h - 1)))
            else:
                fx, fy = cx_center, cy_center

            dx = fx - x
            dy = fy - y
            dist2 = dx * dx + dy * dy
            if dist2 < 1e-6:
                dist2 = 1e-6
            dist = math.sqrt(dist2)

            # : optional radius limit for point forces
            try:
                radius = float(f.get('radius', 0.0) or 0.0)
            except Exception:
                radius = 0.0
            rv = str(f.get('radius_var','') or '').strip()
            if rv:
                try:
                    radius *= float(_get_number_var_ref(params, state, rv, 1.0))
                except Exception:
                    pass
            if radius > 0.0 and dist > radius:
                continue

            ux = dx / dist
            uy = dy / dist
            mag = strength / dist2
            mag = clamp(mag, -4.0, 4.0)
            vx += ux * mag
            vy += uy * mag

        # Friction (simple exponential-ish)
        if fr > 0.0:
            damp = max(0.0, 1.0 - fr * dt)
            vx *= damp
            vy *= damp

        # Clamp velocity
        vx = clamp(vx, -max_v, max_v)
        vy = clamp(vy, -max_v, max_v)

        x += vx * dt * 10.0
        y += vy * dt * 10.0

        # : world bounds interaction + events
        emode = str(params.get('edge_mode','') or '').lower().strip()
        if not emode:
            emode = 'wrap' if bool(params.get('wrap_edges', True)) else 'bounce'
        if emode == 'wrap':
            if w > 1:
                while x < 0.0:
                    x += float(w)
                    wrap_count += 1
                while x >= float(w):
                    x -= float(w)
                    wrap_count += 1
            else:
                x = 0.0
            if h > 1:
                while y < 0.0:
                    y += float(h)
                    wrap_count += 1
                while y >= float(h):
                    y -= float(h)
                    wrap_count += 1
            else:
                y = 0.0
        elif emode == 'destroy':
            out = (x < 0.0) or (x > float(w - 1)) or (y < 0.0) or (y > float(h - 1))
            if out:
                bounds_exit_count += 1
                killed += 1
                try:
                    p['_kill'] = True
                except Exception:
                    pass
                continue
        else:
            # Bounce (default)
            if x < 0.0:
                x = 0.0
                vx = abs(vx)
                wall_hit_count += 1
            if x > float(w - 1):
                x = float(w - 1)
                vx = -abs(vx)
                wall_hit_count += 1
            if y < 0.0:
                y = 0.0
                vy = abs(vy)
                wall_hit_count += 1
            if y > float(h - 1):
                y = float(h - 1)
                vy = -abs(vy)
                wall_hit_count += 1
        p['x'], p['y'], p['vx'], p['vy'] = x, y, vx, vy

    # : remove killed particles (bounds destroy mode)
    if killed > 0:
        try:
            parts[:] = [p for p in parts if not bool(p.get('_kill', False))]
        except Exception:
            pass

    # : publish world-bound events
    if isinstance(state, dict) and isinstance(state.get('_events'), dict):
        try: state['_events']['wall_hit'] = int(wall_hit_count)
        except Exception: state['_events']['wall_hit'] = 0
        try: state['_events']['wrap'] = int(wrap_count)
        except Exception: state['_events']['wrap'] = 0
        try: state['_events']['bounds_exit'] = int(bounds_exit_count)
        except Exception: state['_events']['bounds_exit'] = 0
        try:
            state['_events']['despawn'] = int(state['_events'].get('despawn', 0) or 0) + int(bounds_exit_count)
        except Exception:
            pass

    # /46: particle-particle events (collision / proximity) with spatial hash
    pp_mode = str(params.get('pp_mode','off') or 'off').lower().strip()
    try:
        pp_r = float(params.get('pp_radius', 1.25) or 1.25)
    except Exception:
        pp_r = 1.25
    pp_r2 = float(pp_r) * float(pp_r)
    try:
        pp_max = int(params.get('pp_max_pairs', 2000) or 2000)
    except Exception:
        pp_max = 2000
    pp_coll = 0
    pp_near = 0
    if pp_mode != 'off' and pp_r > 0.0 and len(parts) >= 2:
        # Spatial hashing: bucket size = pp_r
        cell = float(pp_r)
        if cell <= 0.0:
            cell = 1.0
        grid = {}  # (cx,cy) -> [index,...]
        for idx_p, p in enumerate(parts):
            try:
                x0 = float(p.get('x', 0.0) or 0.0)
                y0 = float(p.get('y', 0.0) or 0.0)
            except Exception:
                x0, y0 = 0.0, 0.0
            cx = int(math.floor(x0 / cell))
            cy = int(math.floor(y0 / cell))
            grid.setdefault((cx, cy), []).append(idx_p)
        checked = 0
        for (cx, cy), lst in grid.items():
            # Compare within this cell and neighbor cells
            for nx in (cx-1, cx, cx+1):
                for ny in (cy-1, cy, cy+1):
                    lst2 = grid.get((nx, ny))
                    if not lst2:
                        continue
                    for ai in lst:
                        ax = float(parts[ai].get('x', 0.0) or 0.0)
                        ay = float(parts[ai].get('y', 0.0) or 0.0)
                        for bi in lst2:
                            if bi <= ai:
                                continue
                            checked += 1
                            if pp_max > 0 and checked > pp_max:
                                break
                            bx = float(parts[bi].get('x', 0.0) or 0.0)
                            by = float(parts[bi].get('y', 0.0) or 0.0)
                            dx = ax - bx
                            dy = ay - by
                            if (dx*dx + dy*dy) <= pp_r2:
                                if pp_mode in ('near','both'):
                                    pp_near += 1
                                if pp_mode in ('collision','both'):
                                    pp_coll += 1
                        if pp_max > 0 and checked > pp_max:
                            break
                    if pp_max > 0 and checked > pp_max:
                        break
                if pp_max > 0 and checked > pp_max:
                    break
            if pp_max > 0 and checked > pp_max:
                break
    if isinstance(state, dict) and isinstance(state.get('_events'), dict):
        try: state['_events']['pp_collision'] = int(pp_coll)
        except Exception: state['_events']['pp_collision'] = 0
        try: state['_events']['pp_near'] = int(pp_near)
        except Exception: state['_events']['pp_near'] = 0

    # Rules: overlap check (particle collects any enabled target)
    hit_count = 0
    if targets_cfg and w > 0 and h > 0:
        for i, cfg in enumerate(targets_cfg):
            if not bool(cfg.get("enabled", True)):
                continue
            dx = st_targets[i].get("x"); dy = st_targets[i].get("y")
            if dx is None or dy is None:
                continue
            hit = False
            for p in parts:
                try:
                    xi = int(round(float(p.get("x", 0.0))))
                    yi = int(round(float(p.get("y", 0.0))))
                except Exception:
                    continue
                if xi == int(dx) and yi == int(dy):
                    hit = True
                    break
            if hit:
                hit_count += 1
                try:
                    state["score"] = int(state.get("score", 0)) + 1
                except Exception:
                    state["score"] = 1
                _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
                dot = state.get("dot") or {}
                st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
                st_targets[i]["timer"] = 0.0

    # ---- : Publish events + apply rules after event detection ----
    if isinstance(state, dict) and isinstance(state.get('_events'), dict):
        state['_events']['target_hit'] = int(hit_count)
    _apply_rules(state, params.get("_rules"), float(dt), events=(state.get('_events') if isinstance(state, dict) else None), params=params)


    # : monotonic rule time for cooldowns
    try:
        state['_rule_time'] = float(state.get('_rule_time', 0.0) or 0.0) + float(dt or 0.0)
    except Exception:
        state['_rule_time'] = 0.0

def _update_broken(*,state: EffectState, params: dict, dt: float, t: float, audio: dict | None = None) -> None:
    # Determine bounds from cached layout
    try:
        w = int(state.get("w", 60))
        h = int(state.get("h", 1))
    except Exception:
        w, h = 60, 1

    # ---- /17: Variables + Rules ----
    # Initialize an event bag early so triggers are stable, and sync variables
    # before any variable-bound params are computed.
    if isinstance(state, dict):
        state['_events'] = {'target_hit': 0, 'collision': 0, 'spawn': 0, 'despawn': 0}
    _sync_variables(state, params.get("_vars_def"))
    # Legacy: enemy_count is still the base "initial/target" count.
    base_count = int(params.get("enemy_count", 24) or 24)
    cv = str(params.get("enemy_count_bind_var", "") or "").strip()
    if cv:
        try:
            base_count = int(round(float(base_count) * float(_get_number_var_ref(params, state, cv, 1.0))))
        except Exception:
            pass
    base_count = max(0, min(200, base_count))

    # : Continuous spawning (spawn_rate) + max_entities cap, both optionally bindable.
    max_entities = int(params.get("max_entities", base_count) or base_count)
    mv = str(params.get("max_entities_bind_var", "") or "").strip()
    if mv:
        try:
            max_entities = int(round(float(max_entities) * float(_get_number_var_ref(params, state, mv, 1.0))))
        except Exception:
            pass
    max_entities = max(0, min(200, max_entities))

    spawn_rate = float(params.get("spawn_rate", 0.0) or 0.0)
    sv = str(params.get("spawn_rate_bind_var", "") or "").strip()
    if sv:
        try:
            spawn_rate = float(spawn_rate) * float(_get_number_var_ref(params, state, sv, 1.0))
        except Exception:
            pass
    if spawn_rate < 0.0:
        spawn_rate = 0.0

    _ensure_state(state, w=w, h=h)
    parts = state.get("p") or []


    # : per-tick events for rule triggers
    try:
        state['_events'] = {'spawn': 0, 'despawn': 0}
    except Exception:
        pass


    # : Detect significant param changes and re-seed so changes are immediately visible.
    try:
        sig = (
            float(spawn_rate),
            int(max_entities),
            int(base_count),
            float(lifetime),
        )
        if state.get("_sig") != sig:
            state["_sig"] = sig
            state["_seeded_particles"] = False
            state["spawn_accum"] = 0.0
    except Exception:
        pass

    rng: DeterministicRNG = state.get("rng")  # type: ignore


    # : Particle lifetime (seconds). 0 means immortal.
    lifetime = float(params.get("lifetime", 0.0) or 0.0)
    lv = str(params.get("lifetime_bind_var", "") or "").strip()
    if lv:
        try:
            lifetime = float(lifetime) * float(_get_number_var_ref(params, state, lv, 1.0))
        except Exception:
            pass
    if lifetime < 0.0:
        lifetime = 0.0


    # Seed particles once so demo is immediately visible.
    if isinstance(state, dict) and not state.get("_seeded_particles"):
        seed = base_count
        if spawn_rate > 0.0:
            seed = min(base_count, max_entities)
        try:
            for _ in range(int(seed)):
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try:
                    state['_events']['spawn'] += 1
                except Exception:
                    pass
        except Exception:
            pass
        state["_seeded_particles"] = True


    # : Burst spawning requested by Rules (state['_burst'] integer).
    try:
        burst_n = int(state.get('_burst', 0) or 0) if isinstance(state, dict) else 0
    except Exception:
        burst_n = 0
    if burst_n > 0 and w > 0 and h > 0:
        try:
            cap = max_entities if max_entities > 0 else 200
            burst_n = min(burst_n, max(0, cap - len(parts)))
            for _ in range(int(burst_n)):
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try:
                    state['_events']['spawn'] += 1
                except Exception:
                    pass
        except Exception:
            pass
        try:
            state['_burst'] = 0
        except Exception:
            pass

    # If spawn_rate is enabled, we spawn incrementally up to max_entities.
    # Otherwise, we use legacy "target count" but adjust without hard reset.
    if spawn_rate > 0.0:
        try:
            state["spawn_accum"] = float(state.get("spawn_accum", 0.0)) + float(spawn_rate) * float(dt)
        except Exception:
            state["spawn_accum"] = 0.0
        # Spawn whole particles from accumulator
        try:
            while float(state.get("spawn_accum", 0.0)) >= 1.0 and len(parts) < max_entities:
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try:
                    state['_events']['spawn'] += 1
                except Exception:
                    pass
                state["spawn_accum"] = float(state.get("spawn_accum", 0.0)) - 1.0
        except Exception:
            pass
        # Despawn extras if cap reduced
        if len(parts) > max_entities:
            del parts[max_entities:]
    else:
        target = base_count
        # Soft adjust toward target count (no hard reset)
        if len(parts) < target:
            add_n = min(target - len(parts), max(1, int(round(12 * float(dt)))))
            for _ in range(add_n):
                parts.append(_spawn_particle(rng, w, h, spawn_mask))
                try:
                    state['_events']['spawn'] += 1
                except Exception:
                    pass
        elif len(parts) > target:
            rem_n = min(len(parts) - target, max(1, int(round(12 * float(dt)))))
            if rem_n > 0:
                del parts[-rem_n:]
                try:
                    state['_events']['despawn'] += int(rem_n)
                except Exception:
                    pass




    # : Advance ages and prune expired particles (no hard reset).
    if lifetime > 0.0:
        try:
            for p in parts:
                try:
                    p["age"] = float(p.get("age", 0.0)) + float(dt)
                except Exception:
                    p["age"] = float(dt)
            # Keep only those not expired
            _prev_len = len(parts)
            parts[:] = [p for p in parts if float(p.get("age", 0.0)) <= float(lifetime)]
            try:
                state['_events']['despawn'] += max(0, int(_prev_len - len(parts)))
            except Exception:
                pass
        except Exception:
            pass
    else:
        # still maintain age for completeness
        try:
            for p in parts:
                if "age" in p:
                    p["age"] = float(p.get("age", 0.0)) + float(dt)
        except Exception:
            pass



    # : If continuous spawning is enabled and we're empty, spawn at least one immediately
    # so the user sees a response after changing settings.
    if spawn_rate > 0.0 and max_entities > 0 and len(parts) == 0:
        try:
            parts.append(_spawn_particle(rng, w, h, spawn_mask))
            try:
                state['_events']['spawn'] += 1
            except Exception:
                pass
        except Exception:
            pass



    # : Mirror resolved sim knobs into vars so the existing preview overlay shows them.
    # (Prefix with '_' so they're clearly debug-only.)
    try:
        vmap = state.get("vars")
        if isinstance(vmap, dict):
            vmap["_particles"] = float(len(parts))
            vmap["_spawn_rate"] = float(spawn_rate)
            vmap["_max_entities"] = float(max_entities)
            vmap["_lifetime"] = float(lifetime)
    except Exception:
        pass

    # Rules: normalize targets
    targets_cfg = _get_targets_from_params(params)

    # Maintain a simple occupied set (rounded particle cells)
    occupied: set[int] = set()
    if targets_cfg and w > 0 and h > 0:
        for p in parts:
            try:
                xi = int(round(float(p.get("x", 0.0))))
                yi = int(round(float(p.get("y", 0.0))))
            except Exception:
                continue
            if 0 <= xi < w and 0 <= yi < h:
                occupied.add(yi * w + xi)

    # : Collision zone/group support via injected _target_mask (from PreviewEngine)
    try:
        tmask = params.get('_target_mask')
        if isinstance(tmask, list) and tmask:
            tset = {int(x) for x in tmask if isinstance(x, int) or str(x).isdigit()}
            hit_n = 0
            try:
                hit_n = len(occupied.intersection(tset)) if occupied else 0
            except Exception:
                hit_n = 0
            if isinstance(state, dict):
                ev = state.get('_events')
                if isinstance(ev, dict):
                    ev['collision'] = int(hit_n)
                    ev['target_hit'] = int(ev.get('target_hit',0) or 0) + int(hit_n)
    except Exception:
        pass

    # Ensure state targets list matches config length
    st_targets = state.get("targets")
    if not isinstance(st_targets, list):
        st_targets = []
    # Resize state list
    if len(st_targets) != len(targets_cfg):
        st_targets = [{"x": None, "y": None, "timer": 0.0} for _ in range(len(targets_cfg))]
        state["targets"] = st_targets

    # Tick + spawn targets
    for i, cfg in enumerate(targets_cfg):
        if not bool(cfg.get("enabled", True)):
            continue
        try:
            st_targets[i]["timer"] = float(st_targets[i].get("timer", 0.0)) + float(dt)
        except Exception:
            st_targets[i]["timer"] = 0.0

        dx = st_targets[i].get("x"); dy = st_targets[i].get("y")
        missing = (dx is None) or (dy is None)
        mode = str(cfg.get("mode", "on_hit") or "on_hit").lower().strip()
        interval = float(cfg.get("interval", 1.0) or 1.0)
        if interval < 0.0:
            interval = 0.0
        if missing:
            _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
            # _spawn_dot writes state['dot'], so map it into this slot
            dot = state.get("dot") or {}
            st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
            st_targets[i]["timer"] = 0.0
        elif mode == "timer" and interval > 0.0 and float(st_targets[i].get("timer", 0.0)) >= interval:
            _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
            dot = state.get("dot") or {}
            st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
            st_targets[i]["timer"] = 0.0

    # (Rules run after the hit check below; trigger-based rules use state['_events']).

    spd = float(params.get("speed", 1.0) or 1.0)
    # : optional variable binding for speed
    svb = str(params.get("speed_bind_var", "") or "").strip()
    if svb:
        try:
            spd *= float(_get_number_var_ref(params, state, svb, 1.0))
        except Exception:
            pass

    # ---- : Multiple forces ----
    # If params['forces'] exists, use it. Otherwise, fall back to legacy single-force params.
    forces = state.get('_forces') if isinstance(state.get('_forces'), list) else params.get("forces")
    if not isinstance(forces, list):
        forces = []
        forces.append({
            "kind": "point",
            "mode": str(params.get("force_mode", "attract") or "attract"),
            "strength": float(params.get("gravity", 6.0) or 6.0),
            "radius": 0.0,
            "source": str(params.get("force_source", "center") or "center"),
            "x": float(params.get("source_x", 0.0) or 0.0),
            "y": float(params.get("source_y", 0.0) or 0.0),
            "strength_var": str(params.get("gravity_bind_var", "") or "").strip(),
            "radius_var": "",
            "enabled_var": "",
        })
        if bool(params.get("pairwise_repel", False)):
            forces.append({
                "kind": "separation",
                "strength": float(params.get("repel_strength", 4.0) or 4.0),
                "range": float(params.get("repel_range", 6.0) or 6.0),
                "strength_var": str(params.get("repel_strength_bind_var", "") or "").strip(),
            })

    # Global sim knobs
    fr = float(params.get("friction", 0.0) or 0.0)
    # : optional variable binding for friction
    fvb = str(params.get("friction_bind_var", "") or "").strip()
    if fvb:
        try:
            fr *= float(_get_number_var_ref(params, state, fvb, 1.0))
        except Exception:
            pass
    fr = 0.0 if fr < 0.0 else (10.0 if fr > 10.0 else fr)
    wrap_edges = bool(params.get("wrap_edges", True))

    # Precompute layout center
    cx_center = (float(w - 1) / 2.0) if w > 1 else 0.0
    cy_center = (float(h - 1) / 2.0) if h > 1 else 0.0

    # Apply any separation forces first (pairwise)
    sep_forces = [f for f in forces if isinstance(f, dict) and str(f.get("kind","")) == "separation"]
    for sf in sep_forces:
        try:
            repel_k = float(sf.get("strength", 4.0) or 4.0) * float(spd)
        except Exception:
            repel_k = 0.0
        try:
            repel_range = float(sf.get("range", 6.0) or 6.0)
        except Exception:
            repel_range = 0.0
        if repel_range < 0.0:
            repel_range = 0.0

        rv = str(sf.get("range_var", "") or "").strip()
        if rv:
            try:
                repel_range *= float(_get_number_var_ref(params, state, rv, 1.0))
            except Exception:
                pass
        sv = str(sf.get("strength_var", "") or "").strip()

        if not bool(sf.get('enabled', True)):
            continue
        ev = str(sf.get("enabled_var", "") or "").strip()
        if ev:
            # Toggle variable gating this force
            try:
                if not _get_toggle_var_ref(params, state, ev, False):
                    continue
            except Exception:
                continue
        if sv:
            repel_k *= _get_number_var_ref(params, state, sv, 1.0)
        if repel_k <= 0.0 or repel_range <= 0.0 or len(parts) <= 1:
            continue
        rr2 = float(repel_range) * float(repel_range)
        max_pairs_n = 140
        parts_for_sep = parts if len(parts) <= max_pairs_n else parts[:max_pairs_n]
        for i in range(len(parts_for_sep) - 1):
            pi = parts_for_sep[i]
            xi = float(pi.get("x", 0.0)); yi = float(pi.get("y", 0.0))
            vxi = float(pi.get("vx", 0.0)); vyi = float(pi.get("vy", 0.0))
            for j in range(i + 1, len(parts_for_sep)):
                pj = parts_for_sep[j]
                xj = float(pj.get("x", 0.0)); yj = float(pj.get("y", 0.0))
                dx = xi - xj
                dy = yi - yj
                d2 = dx*dx + dy*dy
                if d2 < 1e-6 or d2 > rr2:
                    continue
                d = math.sqrt(d2)
                ux = dx / d
                uy = dy / d
                mag = (repel_k / d2)
                mag = clamp(mag, 0.0, 2.5)
                vxi += ux * mag
                vyi += uy * mag
                vxj = float(pj.get("vx", 0.0)) - ux * mag
                vyj = float(pj.get("vy", 0.0)) - uy * mag
                pj["vx"], pj["vy"] = vxj, vyj
            pi["vx"], pi["vy"] = vxi, vyi

    # Point forces (attract/repel) are applied per particle below.
    # Integrate (point forces)
    max_v = 25.0
    point_forces = [f for f in forces if isinstance(f, dict) and str(f.get('kind','point')) in ('point','force','attract','repel')]
    for p in parts:
        try:
            x = float(p.get('x', 0.0))
            y = float(p.get('y', 0.0))
            vx = float(p.get('vx', 0.0))
            vy = float(p.get('vy', 0.0))
        except Exception:
            continue

        for f in point_forces:
            try:
                mode = str(f.get('mode', 'attract') or 'attract').lower().strip()
                strength = float(f.get('strength', 0.0) or 0.0) * float(spd)
            except Exception:
                continue
            if mode in ('repel','away','push'):
                strength = -abs(strength)
            else:
                strength = abs(strength)
            sv = str(f.get('strength_var','') or '').strip()

            if not bool(f.get('enabled', True)):
                continue
            ev = str(f.get('enabled_var','') or '').strip()
            if ev:
                try:
                    if not _get_toggle_var_ref(params, state, ev, False):
                        continue
                except Exception:
                    continue
            if sv:
                strength *= _get_number_var_ref(params, state, sv, 1.0)

            src = str(f.get('source', 'center') or 'center').lower().strip()
            if src == 'fixed':
                try:
                    fx = float(f.get('x', cx_center) or cx_center)
                except Exception:
                    fx = cx_center
                try:
                    fy = float(f.get('y', cy_center) or cy_center)
                except Exception:
                    fy = cy_center
                fx = clamp(fx, 0.0, float(max(0, w - 1)))
                fy = clamp(fy, 0.0, float(max(0, h - 1)))
            else:
                fx, fy = cx_center, cy_center

            dx = fx - x
            dy = fy - y
            dist2 = dx * dx + dy * dy
            if dist2 < 1e-6:
                dist2 = 1e-6
            dist = math.sqrt(dist2)

            # : optional radius limit for point forces
            try:
                radius = float(f.get('radius', 0.0) or 0.0)
            except Exception:
                radius = 0.0
            rv = str(f.get('radius_var','') or '').strip()
            if rv:
                try:
                    radius *= float(_get_number_var_ref(params, state, rv, 1.0))
                except Exception:
                    pass
            if radius > 0.0 and dist > radius:
                continue

            ux = dx / dist
            uy = dy / dist
            mag = strength / dist2
            mag = clamp(mag, -4.0, 4.0)
            vx += ux * mag
            vy += uy * mag

        # Friction (simple exponential-ish)
        if fr > 0.0:
            damp = max(0.0, 1.0 - fr * dt)
            vx *= damp
            vy *= damp

        # Clamp velocity
        vx = clamp(vx, -max_v, max_v)
        vy = clamp(vy, -max_v, max_v)

        x += vx * dt * 10.0
        y += vy * dt * 10.0

        if wrap_edges:
            if w > 1:
                while x < 0.0:
                    x += float(w)
                while x >= float(w):
                    x -= float(w)
            else:
                x = 0.0
            if h > 1:
                while y < 0.0:
                    y += float(h)
                while y >= float(h):
                    y -= float(h)
            else:
                y = 0.0
        else:
            # Bounce
            if x < 0.0:
                x = 0.0
                vx = abs(vx)
            if x > float(w - 1):
                x = float(w - 1)
                vx = -abs(vx)
            if y < 0.0:
                y = 0.0
                vy = abs(vy)
            if y > float(h - 1):
                y = float(h - 1)
                vy = -abs(vy)

        p['x'], p['y'], p['vx'], p['vy'] = x, y, vx, vy

    # Rules: overlap check (particle collects any enabled target)
    hit_count = 0
    if targets_cfg and w > 0 and h > 0:
        for i, cfg in enumerate(targets_cfg):
            if not bool(cfg.get("enabled", True)):
                continue
            dx = st_targets[i].get("x"); dy = st_targets[i].get("y")
            if dx is None or dy is None:
                continue
            hit = False
            for p in parts:
                try:
                    xi = int(round(float(p.get("x", 0.0))))
                    yi = int(round(float(p.get("y", 0.0))))
                except Exception:
                    continue
                if xi == int(dx) and yi == int(dy):
                    hit = True
                    break
            if hit:
                hit_count += 1
                try:
                    state["score"] = int(state.get("score", 0)) + 1
                except Exception:
                    state["score"] = 1
                _spawn_dot(state=state, w=w, h=h, exclude_cells=occupied)
                dot = state.get("dot") or {}
                st_targets[i]["x"], st_targets[i]["y"] = dot.get("x"), dot.get("y")
                st_targets[i]["timer"] = 0.0

    # ---- : Publish events + apply rules after event detection ----
    if isinstance(state, dict) and isinstance(state.get('_events'), dict):
        state['_events']['target_hit'] = int(hit_count)
    _apply_rules(state, params.get("_rules"), float(dt), events=(state.get('_events') if isinstance(state, dict) else None), params=params)

def _preview_emit(*, num_leds: int, params: dict, t: float, state: EffectState | None = None) -> List[RGB]:
    n = max(1, int(num_leds))
    out: List[RGB] = [(0, 0, 0)] * n

    # Detect current layout dimensions
    w = int(params.get("_mw", 0) or 0)
    h = int(params.get("_mh", 0) or 0)
    if w <= 0 or h <= 0:
        # Fallback: treat as strip
        w = n
        h = 1

    count = int(params.get("enemy_count", 24) or 24)
    if count < 0:
        count = 0
    if count > 200:
        count = 200

    if state is None:
        state = EffectState()

    _ensure_state(state, w=w, h=h)
    parts = state.get("p") or []

    c = params.get("color", (255, 255, 255))
    br = float(params.get("brightness", 1.0) or 1.0)
    px = _apply_brightness((int(c[0]) & 255, int(c[1]) & 255, int(c[2]) & 255), br)

    # Render particles as single pixels
    for p in parts:
        try:
            x = float(p.get("x", 0.0))
            y = float(p.get("y", 0.0))
        except Exception:
            continue
        xi = int(round(x))
        yi = int(round(y))
        if xi < 0 or yi < 0 or xi >= w or yi >= h:
            continue
        idx = yi * w + xi
        if 0 <= idx < n:
            out[idx] = px

    # Render Target Dots (Rules)
    targets_cfg = _get_targets_from_params(params)
    if targets_cfg:
        st_targets = state.get("targets") if isinstance(state, dict) else None
        if not isinstance(st_targets, list) or len(st_targets) != len(targets_cfg):
            st_targets = [{"x": None, "y": None, "timer": 0.0} for _ in range(len(targets_cfg))]
            if isinstance(state, dict):
                state["targets"] = st_targets
        for i, cfg in enumerate(targets_cfg):
            if not bool(cfg.get("enabled", True)):
                continue
            dot = st_targets[i] if 0 <= i < len(st_targets) else {}
            dx = dot.get("x"); dy = dot.get("y")
            if dx is None or dy is None:
                continue
            try:
                idx = int(dy) * w + int(dx)
                if 0 <= idx < n:
                    dc = cfg.get("color", (0, 255, 0))
                    dpx = _apply_brightness((int(dc[0]) & 255, int(dc[1]) & 255, int(dc[2]) & 255), br)
                    out[idx] = dpx
            except Exception:
                pass
    return out


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # This effect is currently preview-first. Layerstack export will treat unknown
    # behaviors as Solid. We still provide a compliant arduino_emit.
    return "// Force Particles: export via layerstack not yet mapped (preview parity first)\n"


def register_force_particles():
    bd = BehaviorDef(
        "force_particles",
        title="Force Particles (Attract/Repel)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    )
    # Mark stateful + provide tick/update for PreviewEngine
    bd.stateful = True
    bd.update = _update
    return register(bd)