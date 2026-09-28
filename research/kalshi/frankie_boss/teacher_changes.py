"""Teacher changes swapped in over the pinned C15 R2/R3 teachers (Greg, 2026-09-28: "Fix every issue that you listed";
book depth "All levels"; "we said we weren't going to drop unknown trades and other info").

The pinned files (c15_teacher.py, c15_teacher_r3.py) are NOT edited; apply() swaps these functions in for one
preparation (parallel_journal.parallel_walk) and restore() puts the pinned ones back. Each function below is the pinned
one with only the marked changes:

  ALL LEVELS   the cohorts (control _columns, R3 _cohort) take every level of the anchor side, not the top three; the
               dynamics and absorption count an order at any rank, not only rank <= 3; R3's history view keeps every
               level and every order of each observation.
  WHOLE DAY    (Greg, 2026-09-28: "change the teacher code then to not stop"; "shouldn't teacher be ingesting the same
               amount of info as Frankie?") the long horizon no longer stops at 1,024 groups: control columns 4 and 6 and
               R3 columns 8, 10 and 12 cover EVERY group of the day so far (Frankie's context is the whole day). They are
               kept as running totals per side, one group's work per row (a whole-day window recomputed per row would be
               quadratic). A group that would have invalidated a window (missing reference, reset, unknown-side book
               event, unreconciled fill, scope boundary) restarts the running totals after it, since in an unbounded window
               it would otherwise make every later value INVALID for the rest of the day; until 1,024 groups have
               accumulated since the start or a restart the long columns are WINDOW_SHORT, as the pinned rule. The 64-group
               columns are unchanged.
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
    long = _control_long(self, key, history)                                     # WHOLE DAY: every group, running totals
    if anchor is not None and healthy:
        if len(window) >= 64:
            raw[3], raw[5] = self._dynamics(window[-64:], side)
        raw[4], raw[6] = long.values(side)
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


# ---- WHOLE DAY: running totals per side ----------------------------------------------------------------------------
def _dynamics_group(group, side):
    """One group's share of the pinned _dynamics (changed as above): (bad reason or None, added, removed, modifies, lost).
    The pinned window result is bad if any group is bad, else the sums over its groups."""
    added = removed = modifies = lost = 0
    pending_fills = {}
    for e in group:
        m = e['normalized']; effect = e['effect']; before = e['order_before']; after = e['order_after']
        if effect['missing_reference'] or m['action'] == 'R' or (m['action'] == 'A' and effect['removed']):
            return 'MISSING_REFERENCE_OR_RESET', 0, 0, 0, 0
        if m['action'] in ('N', 'T'):
            continue
        if m['side'] not in ('A', 'B'):
            return 'UNKNOWN_SIDE', 0, 0, 0, 0
        oid = m['order_id']
        if m['action'] == 'F':
            if before is None:
                return 'MISSING_REFERENCE', 0, 0, 0, 0
            pending_fills[oid] = pending_fills.get(oid, 0) + m['size']
            continue
        if oid in pending_fills:
            economic_removed = (before['size'] if before else 0) - (after['size'] if after else 0)
            if (m['action'] not in ('C', 'M') or before is None
                    or (after is not None and (before['price_raw'], before['side']) != (after['price_raw'], after['side']))
                    or economic_removed != pending_fills[oid]):
                return 'UNRECONCILED_FILL', 0, 0, 0, 0
            del pending_fills[oid]
        if 'rank_before' not in e or 'rank_after' not in e:
            return 'RANK_UNAVAILABLE', 0, 0, 0, 0
        old_in = before is not None and before['side'] == side and e['rank_before'] is not None
        new_in = after is not None and after['side'] == side and e['rank_after'] is not None
        if m['action'] == 'M' and old_in:
            modifies += 1; lost += int(effect['priority_lost'])
        old = before['size'] if old_in else 0; new = after['size'] if new_in else 0
        delta = new - old
        added += max(0, delta); removed += max(0, -delta)
    if pending_fills:
        return 'UNRECONCILED_FILL', 0, 0, 0, 0
    return None, added, removed, modifies, lost


def _absorption_group(group, side):
    """One group's share of the pinned _absorption's removed and fills (valid only when its dynamics share is)."""
    removed = fills = 0
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
        old_in = before is not None and before['side'] == side and e['rank_before'] is not None
        new_in = after is not None and after['side'] == side and e['rank_after'] is not None
        old = before['size'] if old_in else 0
        new = after['size'] if new_in else 0
        removed += max(0, old - new)
        matched = pending.pop(oid, 0)
        if old_in:
            fills += matched
    return removed, fills


class _SideTotals:
    """Running totals of one side since the day's start or the last restart (WHOLE DAY)."""
    def __init__(self):
        self.groups = 0
        self.added = self.removed = self.modifies = self.lost = 0
        self.abs_removed = self.abs_fills = 0

    def add(self, group, side):
        bad, added, removed, modifies, lost = _dynamics_group(group, side)
        if bad is not None:
            self.__init__()                      # restart after a group that would have invalidated the window
            return
        self.groups += 1
        self.added += added; self.removed += removed; self.modifies += modifies; self.lost += lost
        r, f = _absorption_group(group, side)
        self.abs_removed += r; self.abs_fills += f


class _Long:
    """Per instrument: running totals for both sides, fed each new group once."""
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
        value, State = C.value, C.State
        t = self.sides[side]
        if t.groups < C.K_LONG:
            short = value(state=State.MISSING, reason='WINDOW_SHORT')
            return short, dict(short)
        return (value(math.log1p(t.added) - math.log1p(t.removed)),
                value(t.lost / t.modifies) if t.modifies else value(state=State.MISSING, reason='NO_MODIFIES'))

    def absorption(self, side):
        _, T = _modules()
        t = self.sides[side]
        if t.groups < 1024:
            return T._missing('WINDOW_SHORT')
        if not t.abs_removed:
            return T._missing('NO_REMOVALS')
        if not 0 <= t.abs_fills <= t.abs_removed:
            return T._invalid('UNRECONCILED_FILL')
        return T._value(t.abs_fills / t.abs_removed)


_CONTROL_LONG = None


def _control_long(teacher, key, history):
    """The running totals of this pass's history for this instrument: keyed by the pass's own history deque (a new one
    every iter_raw), so a later preparation never continues an earlier one's totals."""
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


class _Cohort:
    """The R3 cohort from the day's start (or the last restart) followed forward over every later group, per side
    (WHOLE DAY): the pinned _cohort with its start at the first group and its window every group since."""
    def __init__(self, start, side):
        observation = start['observation']
        orders = {o['order_id']: o for o in observation['orders']}
        self.cohort = {oid: orders[oid]['size'] for level in observation['levels'][side] for oid in level['order_ids']}
        self.scope = start['source_member_index'], start['session_id']
        self.alive, self.current, self.groups = set(self.cohort), dict(self.cohort), 0

    def add(self, group):
        """None when the group was followed; else the pinned invalid reason (the caller restarts from this group)."""
        pending = {}
        for e in group:
            m, effect = e['normalized'], e['effect']
            oid, action = m['order_id'], m['action']
            if (e['source_member_index'], e['session_id']) != self.scope:
                return 'SCOPE_BOUNDARY'
            if action == 'R':
                return 'RESET'
            if oid not in self.alive:
                continue
            if effect['missing_reference'] or (action == 'A' and effect['removed']):
                return 'MISSING_REFERENCE'
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if oid in pending:
                before, after = e['order_before'], e['order_after']
                if (action not in ('C', 'M') or before is None
                        or (after is not None and (before['price_raw'], before['side']) != (after['price_raw'], after['side']))
                        or before['size'] - (after['size'] if after else 0) != pending.pop(oid)):
                    return 'UNRECONCILED_FILL'
            if action in ('C', 'M'):
                after = e['order_after']
                if action == 'C' or after is None or after['size'] == 0:
                    self.alive.remove(oid)
                    self.current[oid] = 0
                else:
                    self.current[oid] = after['size']
        if pending:
            return 'UNRECONCILED_FILL'
        self.groups += 1
        return None

    def values(self):
        _, T = _modules()
        if self.groups < 1024:
            return (T._missing('WINDOW_SHORT'),) * 2
        total = sum(self.cohort.values())
        if not total:
            return (T._missing('COHORT_EMPTY'),) * 2
        return (T._value(sum(self.cohort[oid] for oid in self.alive) / total),
                T._value(sum(min(size, self.current[oid]) for oid, size in self.cohort.items()) / total))


class _R3Long:
    def __init__(self):
        self.totals = _Long()
        self.cohorts = dict(A=None, B=None)

    def feed(self, group, previous):
        self.totals.feed(group)
        for side in ('A', 'B'):
            cohort = self.cohorts[side]
            if cohort is None:
                if previous is not None and previous[-1].get('observation') is not None:
                    self.cohorts[side] = _Cohort(previous[-1], side)
                    cohort = self.cohorts[side]
                else:
                    continue
            if cohort.add(group) is not None:
                # restart: the cohort from this group's end, followed from the next group on
                self.cohorts[side] = _Cohort(group[-1], side) if group[-1].get('observation') is not None else None


def r3_iter_raw(self, evidence, *, as_of, source_manifest_hash):
    """The pinned RawJournalTeacherR3.iter_raw with the long horizon over the whole day (WHOLE DAY), the unknown-side
    trades carried (UNKNOWN) and the short horizon unchanged; the content chain, checks and row shape are the pinned ones."""
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
            crossed = (obs['levels']['A'] and obs['levels']['B'] and
                       obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw'])
            if missing is None and (any(obs['integrity'].values()) or crossed):
                missing = T._invalid('LEVEL_INTEGRITY')
            if missing is not None:
                values = [dict(missing) for _ in T.COLUMNS]
            else:
                values[0] = T._absorption(groups[-64:], side) if len(groups) >= 64 else T._missing('WINDOW_SHORT')
                values[2], values[4] = (T._cohort(groups[-65][-1], groups[-64:], side)
                                        if len(groups) > 64 else (T._missing('WINDOW_SHORT'),) * 2)
                values[1] = longs[key].totals.absorption(side)                                  # WHOLE DAY
                cohort = longs[key].cohorts[side]
                values[3], values[5] = cohort.values() if cohort is not None else (T._missing('WINDOW_SHORT'),) * 2
        values = [dict(v, unknown_side_trades=unknown[0], unknown_side_volume=unknown[1]) for v in values]
        yield e, dict(cursor=cursor, source_prefix_hash=e['terminal_prefix_hash'],
                      as_of_ts_recv_ns=last_recv, evidence_content_hash=content, columns=values)


def apply():
    """Swap the changed functions in (idempotent per call pair); returns the sha256 recorded in the provenance."""
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
