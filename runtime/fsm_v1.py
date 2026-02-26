"""Finite State Machine runtime (FSM V1).

Design goals:
- Deterministic, export-safe semantics (pure data + step function).
- No UI coupling; behaviors can embed FSMs into their state dicts.
- Simple but expressive: timeouts, events, variable predicates, and signal predicates.

This module intentionally avoids Python-only conveniences that are hard to port.
The contract is close to what the Arduino exporter could support later:
- States identified by small strings (or ints).
- Transitions are ordered; first match wins.
- Inputs are: dt, now, vars (dict), signals (dict), events (set/list).

Typical usage inside a behavior:

    from runtime.fsm_v1 import FSMV1, StateV1, TransitionV1, step_fsm_v1

    def init_state():
        fsm = FSMV1(
            states={
                'intro': StateV1('intro'),
                'run':   StateV1('run'),
                'win':   StateV1('win'),
            },
            start='intro',
            transitions=[
                TransitionV1(src='intro', dst='run', after_s=2.0),
                TransitionV1(src='run', dst='win', event='goal'),
            ],
        )
        return {'fsm': fsm}

    def update(..., state):
        step_fsm_v1(state['fsm'], dt=dt, now=t, vars=vars, signals=signals, events=events)
        if state['fsm'].current == 'run':
            ...

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple


# ---------- Predicates ----------

Predicate = Callable[[Dict[str, Any], Dict[str, float], Set[str]], bool]


def _as_events(events: Optional[Iterable[str]]) -> Set[str]:
    if events is None:
        return set()
    if isinstance(events, set):
        return events
    return set(list(events))


def pred_var_eq(name: str, value: Any) -> Predicate:
    return lambda vars, signals, events: vars.get(name) == value


def pred_var_gt(name: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(vars.get(name, 0.0)) > float(value)


def pred_var_gte(name: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(vars.get(name, 0.0)) >= float(value)


def pred_var_lt(name: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(vars.get(name, 0.0)) < float(value)


def pred_var_lte(name: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(vars.get(name, 0.0)) <= float(value)


def pred_signal_gt(token: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(signals.get(token, 0.0)) > float(value)


def pred_signal_gte(token: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(signals.get(token, 0.0)) >= float(value)


def pred_signal_lt(token: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(signals.get(token, 0.0)) < float(value)


def pred_signal_lte(token: str, value: float) -> Predicate:
    return lambda vars, signals, events: float(signals.get(token, 0.0)) <= float(value)


def pred_event(name: str) -> Predicate:
    return lambda vars, signals, events: name in events


def pred_all(*preds: Predicate) -> Predicate:
    return lambda vars, signals, events: all(p(vars, signals, events) for p in preds)


def pred_any(*preds: Predicate) -> Predicate:
    return lambda vars, signals, events: any(p(vars, signals, events) for p in preds)


# ---------- Data model ----------


@dataclass
class StateV1:
    """State metadata.

    You can attach `meta` for behavior-specific data (e.g., palette name).
    """

    name: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionV1:
    """A transition from src -> dst.

    Conditions are ANDed:
    - after_s: time spent in current state must be >= after_s
    - event: required event name
    - when: arbitrary predicate

    Ordering matters: first matching transition wins.
    """

    src: str
    dst: str

    # time guard
    after_s: Optional[float] = None

    # event guard (single token)
    event: Optional[str] = None

    # predicate guard
    when: Optional[Predicate] = None

    # optional side-effects hooks (purely for preview runtime; exporter can ignore later)
    on_transition: Optional[Callable[["FSMV1", str, str, Dict[str, Any]], None]] = None

    def matches(
        self,
        fsm: "FSMV1",
        *,
        dt: float,
        now: float,
        vars: Dict[str, Any],
        signals: Dict[str, float],
        events: Set[str],
    ) -> bool:
        if fsm.current != self.src:
            return False
        if self.after_s is not None and fsm.state_time_s < float(self.after_s):
            return False
        if self.event is not None and self.event not in events:
            return False
        if self.when is not None and not self.when(vars, signals, events):
            return False
        return True


@dataclass
class FSMV1:
    """Finite State Machine instance."""

    states: Dict[str, StateV1]
    start: str
    transitions: List[TransitionV1]

    current: str = ""
    previous: str = ""
    entered_at: float = 0.0
    state_time_s: float = 0.0

    # Counters help with narratives
    ticks_in_state: int = 0
    transitions_taken: int = 0

    # arbitrary scratchpad for behaviors
    data: Dict[str, Any] = field(default_factory=dict)

    def ensure_started(self, now: float) -> None:
        if not self.current:
            self.current = self.start
            self.previous = ""
            self.entered_at = float(now)
            self.state_time_s = 0.0
            self.ticks_in_state = 0
            self.transitions_taken = 0

    def reset(self, now: float) -> None:
        self.current = ""
        self.ensure_started(now)


# ---------- Step function ----------


def step_fsm_v1(
    fsm: FSMV1,
    *,
    dt: float,
    now: float,
    vars: Optional[Dict[str, Any]] = None,
    signals: Optional[Dict[str, float]] = None,
    events: Optional[Iterable[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Advance FSM by one tick.

    Returns (current_state, previous_state).

    Notes:
    - `events` are treated as ephemeral: pass in events that occurred this tick.
    - The FSM does not clear/hold events.
    """

    vars = vars or {}
    signals = signals or {}
    ev = _as_events(events)
    ctx = context or {}

    fsm.ensure_started(now)

    # advance timers
    fsm.state_time_s = float(now) - float(fsm.entered_at)
    fsm.ticks_in_state += 1

    # find first matching transition
    for tr in fsm.transitions:
        if tr.matches(fsm, dt=dt, now=now, vars=vars, signals=signals, events=ev):
            prev = fsm.current
            fsm.previous = prev
            fsm.current = tr.dst
            fsm.entered_at = float(now)
            fsm.state_time_s = 0.0
            fsm.ticks_in_state = 0
            fsm.transitions_taken += 1
            if tr.on_transition is not None:
                try:
                    tr.on_transition(fsm, prev, tr.dst, ctx)
                except Exception:
                    # Behaviors should not crash the engine because of side-effect hooks.
                    pass
            break

    return fsm.current, fsm.previous


# ---------- Helpers ----------


def make_phase_fsm_v1(phases: Sequence[Tuple[str, float]], loop: bool = True) -> FSMV1:
    """Create a simple timed phase machine.

    phases: [(name, duration_s), ...]
    loop=True makes last phase go back to first.
    """

    states = {name: StateV1(name) for name, _dur in phases}
    transitions: List[TransitionV1] = []
    for i, (name, dur) in enumerate(phases):
        if i < len(phases) - 1:
            transitions.append(TransitionV1(src=name, dst=phases[i + 1][0], after_s=float(dur)))
        else:
            if loop and len(phases) > 0:
                transitions.append(TransitionV1(src=name, dst=phases[0][0], after_s=float(dur)))
    start = phases[0][0] if phases else ""
    return FSMV1(states=states, start=start, transitions=transitions)
