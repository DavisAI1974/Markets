"""Teacher changes swapped in over the pinned C15 R2/R3 teachers (Greg, 2026-09-28).

  "Fix every issue that you listed"; book depth "All levels"; "we said we weren't going to drop unknown trades and other
  info"; "change the teacher code then to not stop"; "shouldn't teacher be ingesting the same amount of info as
  Frankie?"; "Get rid of your invalid code too ... nothing will be dropped like trades or anything because data is
  incomplete. We just list it and then we can try to fill in missing data later. Zero data gets dropped."

The pinned files (c15_teacher.py, c15_teacher_r3.py, c15_dstate.py) are NOT edited; apply() swaps these functions in for
one preparation (parallel_journal.parallel_walk) and restore() puts the pinned ones back.

  ZERO DROPPED  No value is marked INVALID and no event, trade or group is thrown away because data is incomplete. Every
                value is computed from the data that is there, and what was incomplete is LISTED on it: an "incomplete"
                mapping {reason: count} (missing reference, reset, unknown-side book event, unreconciled fill, rank
                unavailable, left-censored origin, level integrity, scope boundary, fills exceeding removals, ...), so the
                gaps can be filled in later. An event whose side is unknown cannot be put on a side's tally: it is counted
                under UNKNOWN_SIDE (with its quantity) instead of on a side, never dropped and never fatal. MISSING remains
                only where no number exists at all (no flow, no modifies, no removals, an empty cohort, a zero quantity):
                nothing is dropped there, the value simply has not come into being.
  NO MINIMUM    (Greg: "We removed the output limits too. Make both of those changes now") there is no 64- or 1,024-group
                minimum: the anchor, the short window (the last 64 groups, or every group while fewer exist) and the
                whole-day totals are computed from the first group on; the cohorts start from the day's first book.
  ALL LEVELS    The cohorts take every level of the anchor side (not the top three); the dynamics and absorption count
                an order at any rank; R3's history view keeps every level and every order of each observation.
  WHOLE DAY     The long horizon (control columns 4 and 6, R3 columns 8, 10 and 12) covers every group of the day so far
                (Frankie's context is the whole day), as running totals per side, one group's work per row, from the
                first group. Nothing restarts it.
  UNKNOWN       Unknown-side trades never invalidate a window: the anchor comes from the known-side trades and the unknown
                trades' count and volume are carried on every column (unknown_side_trades, unknown_side_volume).
  D             The D machine is fed the book as it is (its integrity flags listed, not used to freeze it). Where the pinned
                machine still returns INVALID (no far price, unknown tick, a zero previous step), the six D columns are
                computed from the chain's own current state (the pinned column rule) and the reason is listed; a zero
                previous step gives the ratio as log1p(m_last) - log1p(m_prev), listed DEGENERATE_STEP. No INVALID.

The provenance says so: parallel_teacher adds this file's sha256 to the candidate digest and the teacher binding while
the changes are applied, so these targets are never labelled as the pinned R3's.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path

CHANGES_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_SAVED = []


def _modules():
    from . import c15_teacher as C
    from . import c15_teacher_r3 as T
    return C, T


def _with(value, incomplete, **extra):
    """A value dict with its incomplete list attached (sorted, whole) and any extra carried fields."""
    out = dict(value, **extra)
    if incomplete:
        out['incomplete'] = dict(sorted(incomplete.items()))
    return out


def _flow(trades):
    """Known-side buy and sell sizes, and the unknown-side trades' count and volume (carried, never fatal)."""
    buy = sum(x['size'] for x in trades if x['side'] == 'B')
    sell = sum(x['size'] for x in trades if x['side'] == 'A')
    unknown = [x for x in trades if x['side'] not in ('A', 'B')]
    return buy, sell, len(unknown), sum(x['size'] for x in unknown)


# ---- one group's shares (dynamics, absorption), every event counted or listed ----------------------------------------
def _dynamics_group(group, side):
    """One group's share of the dynamics: (added, removed, modifies, lost, incomplete Counter). Every event is used:
    an event with a missing reference, a reset or an unreconciled fill is counted from the order state that is there and
    listed; an unknown-side book event is listed under UNKNOWN_SIDE with its quantity (it cannot go on a side)."""
    added = removed = modifies = lost = 0
    incomplete = Counter()
    pending_fills = {}
    for e in group:
        m = e['normalized']; effect = e['effect']; before = e['order_before']; after = e['order_after']
        if effect['missing_reference']:
            incomplete['MISSING_REFERENCE'] += 1
        if m['action'] == 'R':
            incomplete['RESET'] += 1
        if m['action'] == 'A' and effect['removed']:
            incomplete['ADD_REPLACED_EXISTING'] += 1
        if m['action'] in ('N', 'T', 'R'):
            continue
        if m['side'] not in ('A', 'B'):
            incomplete['UNKNOWN_SIDE'] += 1
            incomplete['UNKNOWN_SIDE_QUANTITY'] += int(m['size'] or 0)
            continue
        oid = m['order_id']
        if m['action'] == 'F':
            if before is None:
                incomplete['FILL_WITHOUT_ORDER'] += 1
            pending_fills[oid] = pending_fills.get(oid, 0) + m['size']
            continue
        if oid in pending_fills:
            economic_removed = (before['size'] if before else 0) - (after['size'] if after else 0)
            if (m['action'] not in ('C', 'M') or before is None
                    or (after is not None and (before['price_raw'], before['side']) != (after['price_raw'], after['side']))
                    or economic_removed != pending_fills[oid]):
                incomplete['UNRECONCILED_FILL'] += 1
            del pending_fills[oid]
        if 'rank_before' not in e or 'rank_after' not in e:
            incomplete['RANK_UNAVAILABLE'] += 1
        rank_before, rank_after = e.get('rank_before', 0), e.get('rank_after', 0)
        old_in = before is not None and before['side'] == side and rank_before is not None       # every level
        new_in = after is not None and after['side'] == side and rank_after is not None          # every level
        if m['action'] == 'M' and old_in:
            modifies += 1; lost += int(effect['priority_lost'])
        old = before['size'] if old_in else 0; new = after['size'] if new_in else 0
        delta = new - old
        added += max(0, delta); removed += max(0, -delta)
    if pending_fills:
        incomplete['UNRECONCILED_FILL'] += len(pending_fills)
    return added, removed, modifies, lost, incomplete


def _absorption_group(group, side):
    """One group's removed quantity and the fills matched to it, on every level."""
    removed = fills = 0
    pending = {}
    for e in group:
        m = e['normalized']
        action, oid = m['action'], m['order_id']
        if action == 'F':
            pending[oid] = pending.get(oid, 0) + m['size']
            continue
        if action in ('T', 'N', 'R') or m['side'] not in ('A', 'B'):
            continue                      # listed by the dynamics share (UNKNOWN_SIDE / RESET), never dropped silently
        before, after = e['order_before'], e['order_after']
        old_in = before is not None and before['side'] == side and e.get('rank_before', 0) is not None
        new_in = after is not None and after['side'] == side and e.get('rank_after', 0) is not None
        old = before['size'] if old_in else 0
        new = after['size'] if new_in else 0
        removed += max(0, old - new)
        matched = pending.pop(oid, 0)
        if old_in:
            fills += matched
    return removed, fills


def _dynamics_values(added, removed, modifies, lost, incomplete):
    C, _ = _modules()
    value, State = C.value, C.State
    balance = _with(value(math.log1p(added) - math.log1p(removed)), incomplete)
    loss = _with(value(lost / modifies) if modifies else value(state=State.MISSING, reason='NO_MODIFIES'), incomplete)
    return balance, loss


def _absorption_value(removed, fills, incomplete):
    _, T = _modules()
    incomplete = Counter(incomplete)
    if not removed:
        return _with(T._missing('NO_REMOVALS'), incomplete)
    if fills > removed:
        incomplete['FILLS_EXCEED_REMOVALS'] += 1          # kept and listed; the share is reported as computed
    return _with(T._value(fills / removed), incomplete)


# ---- control (c15_teacher.JournalTeacher) --------------------------------------------------------------------------
def control_dynamics(groups, side):
    added = removed = modifies = lost = 0
    incomplete = Counter()
    for group in groups:
        a, r, m, l, i = _dynamics_group(group, side)
        added += a; removed += r; modifies += m; lost += l; incomplete.update(i)
    return _dynamics_values(added, removed, modifies, lost, incomplete)


def control_columns(self, e, history, origins, key, machines, ordinal):
    C, _ = _modules()
    value, State, COLUMNS, ABLATED_COLUMNS = C.value, C.State, C.COLUMNS, C.ABLATED_COLUMNS
    raw = [value(state=State.ABLATED, reason='UNBUILT_B2_C1') if c in ABLATED_COLUMNS else
           value(state=State.MISSING, reason='WINDOW_SHORT') for c in COLUMNS]
    window = list(history)
    anchor = None; reason = 'WINDOW_SHORT'
    unknown_count = unknown_volume = 0
    if window:                                                   # no minimum: the last 64 groups, or every group so far
        trades = [x['normalized'] for g in window[-C.K_SHORT:] for x in g if x['normalized']['action'] == 'T']
        buy, sell, unknown_count, unknown_volume = _flow(trades)
        reason = 'NO_FLOW' if buy + sell == 0 else 'SIDE_UNDEFINED'
        if buy + sell and abs(buy - sell) * 20 > buy + sell:
            anchor = 1 if buy > sell else -1
    obs = e['observation']; side = 'A' if anchor == 1 else 'B'
    levels = obs['levels'][side] if anchor is not None else []
    orders = {o['order_id']: o for o in obs['orders']}
    cohort = [orders[oid] for level in levels for oid in level['order_ids']]              # every level
    crossed = bool(obs['levels']['A'] and obs['levels']['B'] and
                   obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw'])
    book = Counter({'LEVEL_INTEGRITY_' + str(flag).upper(): 1 for flag, raised in obs['integrity'].items() if raised})
    if crossed:
        book['CROSSED_BOOK'] += 1
    if anchor is None:
        for i in (0, 1, 2, 3, 4, 5, 6): raw[i] = value(state=State.MISSING, reason=reason)
    elif not cohort:
        for i in (0, 1, 2): raw[i] = _with(value(state=State.MISSING, reason='LEVEL_EMPTY'), book)
    else:
        now = e['normalized']['ts_recv_ns']; total = sum(o['size'] for o in cohort)
        front = cohort[0]
        censored = Counter(book)
        if not origins.get((key, front['order_id']), False):
            censored['LEFT_CENSORED_FRONT'] += 1          # its age is a lower bound: the origin is before the journal
        raw[0] = _with(value(math.log1p(max(0, (now - front['priority_recv_ns']) / 1e9))), censored)
        cohort_censored = Counter(book)
        unseen = sum(1 for o in cohort if not origins.get((key, o['order_id']), False))
        if unseen:
            cohort_censored['LEFT_CENSORED_ORDERS'] += unseen
        if total <= 0:
            raw[1] = _with(value(state=State.MISSING, reason='ZERO_QUANTITY'), cohort_censored)
            raw[2] = _with(value(state=State.MISSING, reason='ZERO_QUANTITY'), cohort_censored)
        else:
            cumulative = 0
            for order in sorted(cohort, key=lambda o: now - o['priority_recv_ns']):
                cumulative += order['size']
                if cumulative * 10 >= 9 * total:
                    raw[1] = _with(value(math.log1p(max(0, (now - order['priority_recv_ns']) / 1e9))), cohort_censored); break
            raw[2] = _with(value(sum((o['size'] / total) ** 2 for o in cohort)), book)
    long = _control_long(key, history)
    if anchor is not None:
        raw[3], raw[5] = self._dynamics(window[-64:], side)
        raw[4], raw[6] = long.values(side)
        for i in (3, 4, 5, 6):
            if book:
                raw[i] = _with(raw[i], Counter(raw[i].get('incomplete', {})) + book)
    machine = machines.setdefault(key, C.DChain(tick_raw=self.ticks[key[1]]))
    far = levels[0]['price_raw'] if levels else None
    dout = machine.advance_synthetic(C.DObservation(ordinal, e['source_member_index'], e['session_id'],
        anchor, far, True))                                          # the book as it is; its flags listed below
    columns, listed = dout.columns, Counter(book)
    if any(d.state == 'INVALID' for d in columns):
        listed.update(d.reason for d in columns if d.state == 'INVALID' and d.reason)
        columns = _d_columns(machine._state, listed)
    for i, d in enumerate(columns, 13):
        raw[i] = _with(value(d.value, State[d.state], d.reason or ''), listed)
    raw[0] = dict(raw[0], unknown_side_trades=unknown_count, unknown_side_volume=unknown_volume)
    return raw


def _d_columns(s, listed):
    """The six D columns from the chain's own state, exactly the pinned c15_dstate._columns rule, except that a zero
    previous step gives the ratio as log1p(m_last) - log1p(m_prev) (listed DEGENERATE_STEP) instead of INVALID."""
    from .c15_dstate import DValue
    present = lambda v: DValue(float(v), 'PRESENT')
    missing = DValue(0.0, 'MISSING', 'CHAIN_BROKEN' if s.broken else 'NO_COMPLETED_STEP')
    ratio = missing
    if s.n_ext >= 2:
        if s.m_prev == 0:
            listed['DEGENERATE_STEP'] += 1
            ratio = present(math.log1p(s.m_last) - math.log1p(s.m_prev))
        else:
            ratio = present(math.log(s.m_last / s.m_prev))
    return (present(math.log1p(s.age)), present(math.log1p(s.n_ext)), ratio,
            present(math.log1p(s.p_last)) if s.n_ext >= 1 else missing,
            present(math.log1p(s.duration_last)) if s.n_ext >= 1 else missing,
            present(math.log1p(s.p_prev)) if s.n_ext >= 2 else missing)


# ---- WHOLE DAY: running totals per side ----------------------------------------------------------------------------
class _SideTotals:
    def __init__(self):
        self.groups = 0
        self.added = self.removed = self.modifies = self.lost = 0
        self.abs_removed = self.abs_fills = 0
        self.incomplete = Counter()

    def add(self, group, side):
        added, removed, modifies, lost, incomplete = _dynamics_group(group, side)
        self.groups += 1
        self.added += added; self.removed += removed; self.modifies += modifies; self.lost += lost
        self.incomplete.update(incomplete)
        r, f = _absorption_group(group, side)
        self.abs_removed += r; self.abs_fills += f


class _Long:
    """Per instrument: running totals for both sides over every group of the day, fed each new group once."""
    def __init__(self):
        self.sides = dict(A=_SideTotals(), B=_SideTotals())
        self.seen = None

    def feed(self, group):
        if group is not self.seen:
            for side, totals in self.sides.items():
                totals.add(group, side)
            self.seen = group

    def values(self, side):
        C, _ = _modules()
        t = self.sides[side]
        return _dynamics_values(t.added, t.removed, t.modifies, t.lost, t.incomplete)

    def absorption(self, side):
        _, T = _modules()
        t = self.sides[side]
        return _absorption_value(t.abs_removed, t.abs_fills, t.incomplete)


_CONTROL_LONG = None


def _control_long(key, history):
    """The running totals of this pass's history: keyed by the pass's own history deque (a new one every iter_raw), so a
    later preparation never continues an earlier one's totals."""
    global _CONTROL_LONG
    import weakref
    if _CONTROL_LONG is None:
        _CONTROL_LONG = weakref.WeakKeyDictionary()
    long = _CONTROL_LONG.get(history)
    if long is None:
        long = _CONTROL_LONG[history] = _Long()
    if history:
        long.feed(history[-1])
    return long


# ---- R3 (c15_teacher_r3) --------------------------------------------------------------------------------------------
def r3_anchor(groups):
    _, T = _modules()
    trades = [e['normalized'] for g in groups[-64:] for e in g if e['normalized']['action'] == 'T']   # no minimum
    buy, sell, _, _ = _flow(trades)
    if not buy + sell:
        return None, T._missing('NO_FLOW')
    if abs(buy - sell) * 20 <= buy + sell:
        return None, T._missing('SIDE_UNDEFINED')
    return ('A' if buy > sell else 'B'), None


def r3_absorption(groups, side):
    removed = fills = 0
    incomplete = Counter()
    for group in groups:
        incomplete.update(_dynamics_group(group, side)[4])
        r, f = _absorption_group(group, side)
        removed += r; fills += f
    return _absorption_value(removed, fills, incomplete)


class _Cohort:
    """The cohort of one side's book at a start entry (every level), followed forward group by group; every event is
    followed, and a scope boundary, reset, missing reference or unreconciled fill is LISTED, never fatal."""
    def __init__(self, start, side):
        observation = start['observation']
        orders = {o['order_id']: o for o in observation['orders']}
        self.cohort = {oid: orders[oid]['size'] for level in observation['levels'][side] for oid in level['order_ids']}
        self.scope = start['source_member_index'], start['session_id']
        self.alive, self.current, self.groups = set(self.cohort), dict(self.cohort), 0
        self.incomplete = Counter()

    def add(self, group):
        pending = {}
        for e in group:
            m, effect = e['normalized'], e['effect']
            oid, action = m['order_id'], m['action']
            if (e['source_member_index'], e['session_id']) != self.scope:
                self.incomplete['SCOPE_BOUNDARY'] += 1
            if action == 'R':
                self.incomplete['RESET'] += 1
            if oid not in self.alive:
                continue
            if effect['missing_reference'] or (action == 'A' and effect['removed']):
                self.incomplete['MISSING_REFERENCE'] += 1
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if oid in pending:
                before, after = e['order_before'], e['order_after']
                if (action not in ('C', 'M') or before is None
                        or (after is not None and (before['price_raw'], before['side']) != (after['price_raw'], after['side']))
                        or before['size'] - (after['size'] if after else 0) != pending[oid]):
                    self.incomplete['UNRECONCILED_FILL'] += 1
                del pending[oid]
            if action in ('C', 'M'):
                after = e['order_after']
                if action == 'C' or after is None or after['size'] == 0:
                    self.alive.discard(oid)
                    self.current[oid] = 0
                else:
                    self.current[oid] = after['size']
        if pending:
            self.incomplete['UNRECONCILED_FILL'] += len(pending)
        self.groups += 1

    def values(self):
        _, T = _modules()
        total = sum(self.cohort.values())
        if not total:
            return (_with(T._missing('COHORT_EMPTY'), self.incomplete),) * 2
        return (_with(T._value(sum(self.cohort[oid] for oid in self.alive) / total), self.incomplete),
                _with(T._value(sum(min(size, self.current[oid]) for oid, size in self.cohort.items()) / total), self.incomplete))


def r3_cohort(start, groups, side):
    cohort = _Cohort(start, side)
    for group in groups:
        cohort.add(group)
    return cohort.values()


def r3_history_row(e):
    result = {key: e[key] for key in ('normalized', 'effect', 'order_before', 'order_after',
              'rank_before', 'rank_after', 'source_member_index', 'session_id') if key in e}
    if e['observation'] is not None:
        observation = e['observation']
        result['observation'] = dict(levels={side: list(observation['levels'][side]) for side in ('A', 'B')},  # every level
                                     orders=list(observation['orders']), integrity=observation['integrity'])
    else:
        result['observation'] = None
    return result


class _R3Long:
    def __init__(self):
        self.totals = _Long()
        self.cohorts = dict(A=None, B=None)

    def feed(self, group, previous):
        self.totals.feed(group)
        for side in ('A', 'B'):
            if self.cohorts[side] is None:
                start = previous if previous is not None else group
                if start[-1].get('observation') is None:
                    continue
                self.cohorts[side] = _Cohort(start[-1], side)           # the day's first book, followed from here on
                if start is group:
                    continue                                             # the first group is the start itself
            self.cohorts[side].add(group)


def r3_iter_raw(self, evidence, *, as_of, source_manifest_hash):
    """The pinned RawJournalTeacherR3.iter_raw with the long horizon over the whole day, every level, the unknown-side
    trades carried, nothing INVALID; the content chain, checks and row shape are the pinned ones."""
    from collections import defaultdict, deque
    _, T = _modules()
    if type(as_of) is not int or as_of < 0:
        raise ValueError('nonnegative as_of required')
    for identity in (source_manifest_hash,):
        if (type(identity) is not str or len(identity) != 64
                or any(c not in '0123456789abcdef' for c in identity)):
            raise ValueError('declare source and expected prefix hashes')
    candidate = self.candidate_digest
    history = defaultdict(lambda: deque(maxlen=65))           # the short horizon (64 groups and the one before)
    longs = defaultdict(_R3Long)
    pending = defaultdict(list)
    publishers = {}
    content = T.evidence_hash(dict(candidate=candidate, source=source_manifest_hash))
    last_recv = -1
    for cursor, e in enumerate(evidence):
        if type(e['cursor']) is not int or e['cursor'] != cursor:
            raise ValueError('complete prefix requires every cursor from zero')
        m = e['normalized']
        previous_publisher = publishers.setdefault(m['instrument_id'], m['publisher_id'])
        if previous_publisher != m['publisher_id']:
            raise ValueError('unresolvable publisher scope in instrument-owned book')
        if m['ts_recv_ns'] > as_of:
            raise ValueError('future teacher evidence')
        if m['ts_recv_ns'] < last_recv:
            raise ValueError('receive-time regression')
        last_recv = m['ts_recv_ns']
        content = T.evidence_hash(dict(previous=content, evidence=e))
        key = m['publisher_id'], m['instrument_id']
        pending[key].append(T._history_row(e))
        values = [T._missing('NOT_F_LAST') for _ in T.COLUMNS]
        unknown = (0, 0)
        if e['receipt'] is not None:
            previous = history[key][-1] if history[key] else None
            group = pending.pop(key)
            history[key].append(group)
            longs[key].feed(group, previous)
            groups = list(history[key])
            trades = [x['normalized'] for g in groups[-64:] for x in g if x['normalized']['action'] == 'T']
            _, _, count, volume = _flow(trades)
            unknown = (count, volume)
            side, missing = T._anchor(groups)
            obs = e['observation']
            book = Counter({'LEVEL_INTEGRITY_' + str(flag).upper(): 1 for flag, raised in obs['integrity'].items() if raised})
            if (obs['levels']['A'] and obs['levels']['B'] and
                    obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw']):
                book['CROSSED_BOOK'] += 1
            if missing is not None:
                values = [dict(missing) for _ in T.COLUMNS]
            else:
                values[0] = T._absorption(groups[-64:], side)                       # no minimum: up to the last 64
                start, followed = ((groups[-65][-1], groups[-64:]) if len(groups) > 64 else (groups[0][-1], groups[1:]))
                values[2], values[4] = T._cohort(start, followed, side)
                values[1] = longs[key].totals.absorption(side)                                      # WHOLE DAY
                cohort = longs[key].cohorts[side]
                values[3], values[5] = (cohort.values() if cohort is not None else
                                        (T._missing('NO_BOOK_YET'),) * 2)
                if book:
                    values = [_with(v, Counter(v.get('incomplete', {})) + book) for v in values]
        values = [dict(v, unknown_side_trades=unknown[0], unknown_side_volume=unknown[1]) for v in values]
        yield e, dict(cursor=cursor, source_prefix_hash=e['terminal_prefix_hash'],
                      as_of_ts_recv_ns=last_recv, evidence_content_hash=content, columns=values)


def apply():
    """Swap the changed functions in; returns the sha256 recorded in the provenance."""
    C, T = _modules()
    _SAVED.append((C.JournalTeacher.__dict__['_columns'], C.JournalTeacher.__dict__['_dynamics'], T._anchor,
                   T._absorption, T._cohort, T._history_row, T.RawJournalTeacherR3.__dict__['iter_raw']))
    C.JournalTeacher._columns = control_columns
    C.JournalTeacher._dynamics = staticmethod(control_dynamics)
    T._anchor, T._absorption, T._cohort, T._history_row = r3_anchor, r3_absorption, r3_cohort, r3_history_row
    T.RawJournalTeacherR3.iter_raw = r3_iter_raw
    return CHANGES_SHA256


def restore():
    C, T = _modules()
    columns, dynamics, anchor, absorption, cohort, history_row, iter_raw = _SAVED.pop()
    C.JournalTeacher._columns, C.JournalTeacher._dynamics = columns, dynamics
    T._anchor, T._absorption, T._cohort, T._history_row = anchor, absorption, cohort, history_row
    T.RawJournalTeacherR3.iter_raw = iter_raw
