"""Teacher changes swapped in over the pinned C15 R2/R3 teachers (Greg, 2026-09-28: "Fix every issue that you listed";
book depth "All levels"; "we said we weren't going to drop unknown trades and other info").

The pinned files (c15_teacher.py, c15_teacher_r3.py) are NOT edited; apply() swaps these functions in for one
preparation (parallel_journal.parallel_walk) and restore() puts the pinned ones back. Each function below is the pinned
one with only the marked changes:

  ALL LEVELS   the cohorts (control _columns, R3 _cohort) take every level of the anchor side, not the top three; the
               dynamics and absorption count an order at any rank, not only rank <= 3; R3's history view keeps every
               level and every order of each observation.
  UNKNOWN      a trade whose side is unknown no longer invalidates the window: the anchor comes from the known-side
               trades, and the unknown trades' count and volume are carried on column 0 of the control's raw row
               (keys unknown_side_trades, unknown_side_volume) and on each R3 column (same keys). A book event (not a
               trade) with an unknown side still marks its window INVALID UNKNOWN_SIDE, as before: its effect on the
               book cannot be placed.

The provenance says so: parallel_teacher adds this file's sha256 to the candidate digest and the teacher binding while
the changes are applied, so these targets are never labelled as the pinned R3's.
"""
import hashlib
import math
from pathlib import Path

CHANGES_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_SAVED = []


def _modules():
    from . import c15_teacher as C
    from . import c15_teacher_r3 as T
    return C, T


# ---- control (c15_teacher.JournalTeacher) --------------------------------------------------------------------------
def _flow(trades):
    """Known-side buy and sell sizes, and the unknown-side trades' count and volume (UNKNOWN: carried, not fatal)."""
    buy = sum(x['size'] for x in trades if x['side'] == 'B')
    sell = sum(x['size'] for x in trades if x['side'] == 'A')
    unknown = [x for x in trades if x['side'] not in ('A', 'B')]
    return buy, sell, len(unknown), sum(x['size'] for x in unknown)


def control_columns(self, e, history, origins, key, machines, ordinal):
    C, _ = _modules()
    value, State, COLUMNS, ABLATED_COLUMNS = C.value, C.State, C.COLUMNS, C.ABLATED_COLUMNS
    raw = [value(state=State.ABLATED, reason='UNBUILT_B2_C1') if c in ABLATED_COLUMNS else
           value(state=State.MISSING, reason='WINDOW_SHORT') for c in COLUMNS]
    window = list(history)
    anchor = None; reason = 'WINDOW_SHORT'
    unknown_count = unknown_volume = 0
    if len(window) >= C.K_SHORT:
        trades = [x['normalized'] for g in window[-C.K_SHORT:] for x in g if x['normalized']['action'] == 'T']
        buy, sell, unknown_count, unknown_volume = _flow(trades)          # UNKNOWN: carried, never fatal
        reason = 'NO_FLOW' if buy + sell == 0 else 'SIDE_UNDEFINED'
        if buy + sell and abs(buy - sell) * 20 > buy + sell:
            anchor = 1 if buy > sell else -1
    obs = e['observation']; side = 'A' if anchor == 1 else 'B'
    levels = obs['levels'][side] if anchor is not None else []
    orders = {o['order_id']: o for o in obs['orders']}
    cohort = [orders[oid] for level in levels for oid in level['order_ids']]          # ALL LEVELS
    crossed = (obs['levels']['A'] and obs['levels']['B'] and
               obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw'])
    healthy = not any(obs['integrity'].values()) and not crossed
    if anchor is None:
        for i in (0, 1, 2, 3, 4, 5, 6): raw[i] = value(state=State.MISSING, reason=reason)
    elif not healthy:
        for i in (0, 1, 2, 3, 4, 5, 6): raw[i] = value(state=State.INVALID, reason='LEVEL_INTEGRITY')
    elif not cohort:
        for i in (0, 1, 2): raw[i] = value(state=State.MISSING, reason='LEVEL_EMPTY')
    else:
        now = e['normalized']['ts_recv_ns']; total = sum(o['size'] for o in cohort)
        front = cohort[0]
        raw[0] = (value(math.log1p(max(0, (now - front['priority_recv_ns']) / 1e9)))
                  if origins.get((key, front['order_id']), False) else value(state=State.INVALID, reason='LEFT_CENSORED'))
        if not all(origins.get((key, o['order_id']), False) for o in cohort):
            raw[1] = value(state=State.INVALID, reason='LEFT_CENSORED')
        elif total <= 0:
            raw[1] = value(state=State.INVALID, reason='LEVEL_INTEGRITY')
        else:
            cumulative = 0
            for order in sorted(cohort, key=lambda o: now - o['priority_recv_ns']):
                cumulative += order['size']
                if cumulative * 10 >= 9 * total:
                    raw[1] = value(math.log1p(max(0, (now - order['priority_recv_ns']) / 1e9))); break
        raw[2] = value(sum((o['size'] / total) ** 2 for o in cohort)) if total > 0 else value(state=State.INVALID, reason='LEVEL_INTEGRITY')
    if anchor is not None and healthy:
        for k, bi, mi in ((64, 3, 5), (1024, 4, 6)):
            if len(window) >= k:
                raw[bi], raw[mi] = self._dynamics(window[-k:], side)
    machine = machines.setdefault(key, C.DChain(tick_raw=self.ticks[key[1]]))
    dout = machine.advance_synthetic(C.DObservation(ordinal, e['source_member_index'], e['session_id'],
        anchor, levels[0]['price_raw'] if levels else None, bool(healthy)))
    for i, d in enumerate(dout.columns, 13):
        raw[i] = value(d.value, State[d.state], d.reason or '')
    raw[0] = dict(raw[0], unknown_side_trades=unknown_count, unknown_side_volume=unknown_volume)      # UNKNOWN: carried
    return raw


def control_dynamics(groups, side):
    C, _ = _modules()
    value, State = C.value, C.State
    added = removed = modifies = lost = 0
    for group in groups:
        pending_fills = {}
        for e in group:
            m = e['normalized']; effect = e['effect']; before = e['order_before']; after = e['order_after']
            if effect['missing_reference'] or m['action'] == 'R' or (m['action'] == 'A' and effect['removed']):
                bad = value(state=State.INVALID, reason='MISSING_REFERENCE_OR_RESET'); return bad, bad
            if m['action'] in ('N', 'T'):              # UNKNOWN: a trade's side is flow, not a book event; skipped as before
                continue
            if m['side'] not in ('A', 'B'):
                bad = value(state=State.INVALID, reason='UNKNOWN_SIDE'); return bad, bad
            oid = m['order_id']
            if m['action'] == 'F':
                if before is None:
                    bad = value(state=State.INVALID, reason='MISSING_REFERENCE'); return bad, bad
                pending_fills[oid] = pending_fills.get(oid, 0) + m['size']
                continue
            if oid in pending_fills:
                economic_removed = (before['size'] if before else 0) - (after['size'] if after else 0)
                if (m['action'] not in ('C', 'M') or before is None
                        or (after is not None and (before['price_raw'], before['side']) != (after['price_raw'], after['side']))
                        or economic_removed != pending_fills[oid]):
                    bad = value(state=State.INVALID, reason='UNRECONCILED_FILL'); return bad, bad
                del pending_fills[oid]
            if 'rank_before' not in e or 'rank_after' not in e:
                bad = value(state=State.INVALID, reason='RANK_UNAVAILABLE'); return bad, bad
            old_in = before is not None and before['side'] == side and e['rank_before'] is not None      # ALL LEVELS
            new_in = after is not None and after['side'] == side and e['rank_after'] is not None         # ALL LEVELS
            if m['action'] == 'M' and old_in:
                modifies += 1; lost += int(effect['priority_lost'])
            old = before['size'] if old_in else 0; new = after['size'] if new_in else 0
            delta = new - old
            added += max(0, delta); removed += max(0, -delta)
        if pending_fills:
            bad = value(state=State.INVALID, reason='UNRECONCILED_FILL'); return bad, bad
    return value(math.log1p(added) - math.log1p(removed)), (value(lost / modifies) if modifies else value(state=State.MISSING, reason='NO_MODIFIES'))


# ---- R3 (c15_teacher_r3) --------------------------------------------------------------------------------------------
def r3_anchor(groups):
    _, T = _modules()
    if len(groups) < 64:
        return None, T._missing('WINDOW_SHORT')
    trades = [e['normalized'] for g in groups[-64:] for e in g if e['normalized']['action'] == 'T']
    buy, sell, _, _ = _flow(trades)                      # UNKNOWN: carried, never fatal
    if not buy + sell:
        return None, T._missing('NO_FLOW')
    if abs(buy - sell) * 20 <= buy + sell:
        return None, T._missing('SIDE_UNDEFINED')
    return ('A' if buy > sell else 'B'), None


def r3_absorption(groups, side):
    C, T = _modules()
    dynamics, _ = C.JournalTeacher._dynamics(groups, side)
    if dynamics['state'] == int(T.State.INVALID):
        return T._invalid(dynamics['reason'])
    removed = fills = 0
    for group in groups:
        pending = {}
        for e in group:
            m = e['normalized']
            action, oid = m['action'], m['order_id']
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if action in ('T', 'N'):
                continue
            before, after = e['order_before'], e['order_after']
            old_in = before is not None and before['side'] == side and e['rank_before'] is not None      # ALL LEVELS
            new_in = after is not None and after['side'] == side and e['rank_after'] is not None         # ALL LEVELS
            old = before['size'] if old_in else 0
            new = after['size'] if new_in else 0
            removed += max(0, old - new)
            matched = pending.pop(oid, 0)
            if old_in:
                fills += matched
    if not removed:
        return T._missing('NO_REMOVALS')
    if not 0 <= fills <= removed:
        return T._invalid('UNRECONCILED_FILL')
    return T._value(fills / removed)


def r3_cohort(start, groups, side):
    _, T = _modules()
    observation = start['observation']
    orders = {o['order_id']: o for o in observation['orders']}
    cohort = {oid: orders[oid]['size'] for level in observation['levels'][side]          # ALL LEVELS
              for oid in level['order_ids']}
    return _PINNED['r3_cohort_tail'](cohort, start, groups)


def r3_history_row(e):
    result = {key: e[key] for key in ('normalized', 'effect', 'order_before', 'order_after',
              'rank_before', 'rank_after', 'source_member_index', 'session_id') if key in e}
    if e['observation'] is not None:
        observation = e['observation']
        result['observation'] = dict(levels={side: list(observation['levels'][side]) for side in ('A', 'B')},  # ALL LEVELS
                                     orders=list(observation['orders']), integrity=observation['integrity'])
    else:
        result['observation'] = None
    return result


def _cohort_tail(cohort, start, groups):
    """The pinned _cohort after its cohort is built (unchanged lines), shared by r3_cohort."""
    _, T = _modules()
    scope = start['source_member_index'], start['session_id']
    alive = set(cohort)
    current = dict(cohort)
    for group in groups:
        pending = {}
        for e in group:
            m, effect = e['normalized'], e['effect']
            oid, action = m['order_id'], m['action']
            if (e['source_member_index'], e['session_id']) != scope:
                return (T._invalid('SCOPE_BOUNDARY'),) * 2
            if action == 'R':
                return (T._invalid('RESET'),) * 2
            if oid not in alive:
                continue
            if effect['missing_reference'] or (action == 'A' and effect['removed']):
                return (T._invalid('MISSING_REFERENCE'),) * 2
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if oid in pending:
                before, after = e['order_before'], e['order_after']
                if (action not in ('C', 'M') or before is None
                        or (after is not None and (before['price_raw'], before['side'])
                            != (after['price_raw'], after['side']))
                        or before['size'] - (after['size'] if after else 0) != pending.pop(oid)):
                    return (T._invalid('UNRECONCILED_FILL'),) * 2
            if action in ('C', 'M'):
                after = e['order_after']
                if action == 'C' or after is None or after['size'] == 0:
                    alive.remove(oid)
                    current[oid] = 0
                else:
                    current[oid] = after['size']
        if pending:
            return (T._invalid('UNRECONCILED_FILL'),) * 2
    total = sum(cohort.values())
    if not total:
        return (T._missing('COHORT_EMPTY'),) * 2
    return (T._value(sum(cohort[oid] for oid in alive) / total),
            T._value(sum(min(size, current[oid]) for oid, size in cohort.items()) / total))


_PINNED = dict(r3_cohort_tail=_cohort_tail)


def r3_iter_raw_unknown(pinned_iter_raw):
    """R3 iter_raw with the unknown-side trade count and volume of the anchor window carried on every column."""
    def iter_raw(self, evidence, *, as_of, source_manifest_hash):
        history = {}
        for e, row in pinned_iter_raw(self, _Tee(evidence, history), as_of=as_of, source_manifest_hash=source_manifest_hash):
            counts = history.pop('last', (0, 0))
            row = dict(row, columns=[dict(v, unknown_side_trades=counts[0], unknown_side_volume=counts[1]) for v in row['columns']])
            yield e, row
    return iter_raw


class _Tee:
    """Passes evidence through unchanged and keeps, per instrument, the last 64 groups' trades to count unknown sides."""
    def __init__(self, evidence, out):
        from collections import defaultdict, deque
        self.evidence, self.out = evidence, out
        self.groups = defaultdict(lambda: deque(maxlen=64))
        self.pending = defaultdict(list)

    def __iter__(self):
        for e in self.evidence:
            m = e['normalized']
            key = m['publisher_id'], m['instrument_id']
            if m['action'] == 'T':
                self.pending[key].append(m)
            if e['receipt'] is not None:
                self.groups[key].append(self.pending.pop(key, []))
                trades = [t for g in self.groups[key] for t in g]
                _, _, count, volume = _flow(trades)
                self.out['last'] = (count, volume)
            else:
                self.out['last'] = (0, 0)
            yield e


def apply():
    """Swap the changed functions in (idempotent per call pair); returns the sha256 recorded in the provenance."""
    C, T = _modules()
    _SAVED.append((C.JournalTeacher.__dict__['_columns'], C.JournalTeacher.__dict__['_dynamics'], T._anchor,
                   T._absorption, T._cohort, T._history_row, T.RawJournalTeacherR3.__dict__['iter_raw']))
    C.JournalTeacher._columns = control_columns
    C.JournalTeacher._dynamics = staticmethod(control_dynamics)
    T._anchor, T._absorption, T._cohort, T._history_row = r3_anchor, r3_absorption, r3_cohort, r3_history_row
    T.RawJournalTeacherR3.iter_raw = r3_iter_raw_unknown(_SAVED[-1][6])
    return CHANGES_SHA256


def restore():
    C, T = _modules()
    columns, dynamics, anchor, absorption, cohort, history_row, iter_raw = _SAVED.pop()
    C.JournalTeacher._columns, C.JournalTeacher._dynamics = columns, dynamics
    T._anchor, T._absorption, T._cohort, T._history_row = anchor, absorption, cohort, history_row
    T.RawJournalTeacherR3.iter_raw = iter_raw
