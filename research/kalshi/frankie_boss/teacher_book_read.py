"""The teacher's book read beside the pinned event flow (Greg, 2026-10-09: "the issue is the worker not reading them";
"read beside the pinned functions, never reconstruct/rewrite them").

The pinned teacher measures (c15_teacher / c15_teacher_r3 with teacher_changes) are EVENT-derived: they count each
event's order_before / order_after / rank. Every group's closing row also carries the full book (every level, every
order: teacher_changes.r3_history_row), and the book before the group is the closing book of the previous group. This
module reads those books whole, additively; nothing pinned is called differently or replaced:

  book_group(previous, group)   one group, both sides, every level:
      book      added / removed quantity, modifies (an order on the side in both books whose price or size changed),
                fills matched (the group's F quantity per order, up to the quantity the book shows removed from it)
      events    the event-derived counterparts on the same group: teacher_changes._dynamics_group (added, removed,
                modifies, priority lost, its incomplete listing) and _absorption_group (removed, fills)
      differs   the reconciliation: for added, removed, modifies and fills, every difference between book and events
                with the reasons this group shows (no previous book, several events on one order, an order added and
                gone inside the group, a reset, a missing reference, an unknown side, an event order without a rank
                (the event flow does not count it on the side), a priority-only modify, a book integrity flag, an order
                a level names that the book's orders lack; else UNEXPLAINED)
      depth     the closing book's full depth: per side, every level (price, resting size, order count)
      touches   per event: the level, queue position and the size resting beyond that level, before the group and
                after it (a group's intermediate books are not observed: before/after are the group's two books)
      listing   what is incomplete in the two books (missing book, integrity flags, crossed, orders not in the book)
  window(results, side)         the sum of consecutive groups' results on one side (the pinned windows: the 64-group
                window, the 1,024-group window of the pinned R3, the whole day), with the book counterparts of the
                pinned balance and absorption as value dicts carrying their incomplete listing, and the reconciliation

Values are plain ints, floats, strings, tuples and dicts; a quantity with no number has state MISSING and its reason,
exactly like the pinned columns. FORMAT is bumped only when this shape changes.
"""
from collections import Counter
import math

FORMAT = 1
SCHEMA = 'FRANKIE_TEACHER_BOOK_READ_V1'
MEASURES = ('added', 'removed', 'modifies', 'fills')
SIDES = ('A', 'B')


def _view(row, side, listing):
    """{oid: (level index, queue position, price, size or None)}, [(price, size, count)...], beyond[level] of one side of
    a row's observation (None when the row carries no book)."""
    observation = row.get('observation') if isinstance(row, dict) else None
    if not isinstance(observation, dict):
        return None
    orders = {o['order_id']: o for o in observation.get('orders') or ()}
    state, depth = {}, []
    for li, level in enumerate((observation.get('levels') or {}).get(side) or ()):
        total = 0
        ids = level['order_ids']
        for qi, oid in enumerate(ids):
            order = orders.get(oid)
            if order is None:
                listing['ORDER_NOT_IN_BOOK_ORDERS'] += 1
                state[oid] = (li, qi, level['price_raw'], None)
                continue
            total += order['size']
            state[oid] = (li, qi, level['price_raw'], order['size'])
        depth.append((level['price_raw'], total, len(ids)))
    beyond, running = [0] * len(depth), 0
    for li in range(len(depth) - 1, -1, -1):
        beyond[li] = running
        running += depth[li][1]
    return state, tuple(depth), beyond


def _flags(row, which, listing):
    observation = row.get('observation') if isinstance(row, dict) else None
    if not isinstance(observation, dict):
        listing['NO_BOOK_' + which] += 1
        return
    for flag, raised in (observation.get('integrity') or {}).items():
        if raised:
            listing['BOOK_INTEGRITY_%s_%s' % (str(flag).upper(), which)] += 1
    levels = observation.get('levels') or {}
    if levels.get('A') and levels.get('B') and levels['B'][0]['price_raw'] >= levels['A'][0]['price_raw']:
        listing['CROSSED_BOOK_' + which] += 1


def _depth(levels):
    """A side's (price, size, count) per level as int64 triples (encoding 'int64x3', the bytes of array('q')), or the
    tuple itself (encoding 'tuple') when a value is not an int64; decode with depth_levels()."""
    from array import array
    try:
        if all(type(v) is int for level in levels for v in level):
            return dict(encoding='int64x3', levels=len(levels),
                        data=array('q', [v for level in levels for v in level]).tobytes())
    except OverflowError:
        pass
    return dict(encoding='tuple', levels=len(levels), data=levels)


def depth_levels(depth):
    """[(price, size, count)...] of one side's depth record."""
    from array import array
    if depth is None:
        return None
    if depth['encoding'] == 'tuple':
        return list(depth['data'])
    flat = array('q')
    flat.frombytes(depth['data'])
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


def book_group(previous, group):
    """The book read of one group (previous: the closing row of the key's previous group, or None)."""
    from .teacher_changes import _dynamics_group, _absorption_group
    listing = Counter()
    closing = group[-1] if group else None
    if previous is None:
        listing['NO_PREVIOUS_BOOK'] += 1
    else:
        _flags(previous, 'BEFORE', listing)
    if closing is not None:
        _flags(closing, 'AFTER', listing)
    events = Counter()
    fills = Counter()
    for row in group:
        m = row['normalized']
        events[m['order_id']] += 1
        if m['action'] == 'F':
            fills[m['order_id']] += m['size']
    flow = dict(reset=any(r['normalized']['action'] == 'R' for r in group),
                missing_reference=any(r['effect'].get('missing_reference') for r in group),
                unknown_side=any(r['normalized']['side'] not in SIDES and r['normalized']['action'] not in ('N', 'T', 'R')
                                 for r in group),
                priority_only=any(r['normalized']['action'] == 'M' and r['order_before'] is not None
                                  and r['order_after'] is not None
                                  and (r['order_before']['size'], r['order_before']['price_raw'])
                                  == (r['order_after']['size'], r['order_after']['price_raw']) for r in group),
                netting=any(count > 1 for oid, count in events.items() if oid))
    sides, depth, views = {}, {}, {}
    for side in SIDES:
        before = _view(previous, side, listing) if previous is not None else None
        after = _view(closing, side, listing) if closing is not None else None
        views[side] = (before, after)
        depth[side] = _depth(after[1]) if after is not None else None
        P = before[0] if before is not None else {}
        C = after[0] if after is not None else {}
        added = removed = modifies = matched = 0
        for oid, (_, _, price, size) in C.items():
            old = P.get(oid)
            added += max(0, (size or 0) - ((old[3] or 0) if old is not None else 0))
            if old is not None and (old[2], old[3]) != (price, size):
                modifies += 1
        for oid, (_, _, price, size) in P.items():
            now = C.get(oid)
            gone = max(0, (size or 0) - ((now[3] or 0) if now is not None else 0))
            removed += gone
            if fills.get(oid):
                matched += min(fills[oid], gone)
        e_added, e_removed, e_modifies, e_lost, e_incomplete = _dynamics_group(group, side)
        a_removed, a_fills = _absorption_group(group, side)
        book = dict(added=added, removed=removed, modifies=modifies, fills=matched)
        flowed = dict(added=e_added, removed=e_removed, modifies=e_modifies, fills=a_fills)
        differs = {}
        for measure in MEASURES:
            if book[measure] == flowed[measure]:
                continue
            reasons = Counter()
            if before is None:
                reasons['NO_PREVIOUS_BOOK'] += 1
            if after is None:
                reasons['NO_BOOK_AFTER'] += 1
            if flow['netting']:
                reasons['SEVERAL_EVENTS_ON_ONE_ORDER'] += 1
            if any(oid and oid not in P and oid not in C for oid in events
                   if any(r['normalized']['order_id'] == oid and (r['normalized']['side'] == side or (
                       r['order_before'] or r['order_after'] or {}).get('side') == side) for r in group)):
                reasons['ORDER_ADDED_AND_GONE_IN_GROUP'] += 1
            if flow['reset']:
                reasons['RESET'] += 1
            if flow['missing_reference']:
                reasons['MISSING_REFERENCE'] += 1
            if flow['unknown_side']:
                reasons['UNKNOWN_SIDE'] += 1
            if any((r['order_before'] is not None and r['order_before'].get('side') == side
                    and r.get('rank_before') is None) or (r['order_after'] is not None
                    and r['order_after'].get('side') == side and r.get('rank_after') is None) for r in group):
                reasons['EVENT_ORDER_WITHOUT_RANK'] += 1
            if measure == 'modifies' and flow['priority_only']:
                reasons['PRIORITY_ONLY_MODIFY'] += 1
            if measure == 'fills' and a_removed != removed:
                reasons['REMOVED_DIFFERS'] += 1
            for name in listing:
                if name.startswith(('BOOK_INTEGRITY', 'CROSSED_BOOK', 'ORDER_NOT_IN_BOOK')):
                    reasons[name] += 1
            if not reasons:
                reasons['UNEXPLAINED'] += 1
            differs[measure] = dict(book=book[measure], events=flowed[measure], reasons=dict(sorted(reasons.items())))
        sides[side] = dict(book=book, events=dict(flowed, lost=e_lost, absorption_removed=a_removed),
                           differs=differs, incomplete=dict(sorted(e_incomplete.items())))
    touches = []
    for index, row in enumerate(group):
        m = row['normalized']
        side = m['side'] if m['side'] in SIDES else None
        place = []
        for which in (0, 1):
            view = views[side][which] if side is not None else None
            at = view[0].get(m['order_id']) if view is not None else None
            place.append(None if at is None else (at[0], at[1], view[2][at[0]]))
        touches.append((index, m['order_id'], m['action'], m['side'], place[0], place[1]))
    return dict(format=FORMAT, sides=sides, depth=depth, touches=tuple(touches), listing=dict(sorted(listing.items())))


def _empty():
    return dict(book=Counter(), events=Counter(), reasons={m: Counter() for m in MEASURES}, incomplete=Counter(),
                listing=Counter(), groups=0, not_read=0)


def add(total, result, side):
    """Add one group's result (or None: a group with no book read) to a running total on `side`."""
    if result is None:
        total['not_read'] += 1
        return total
    part = result['sides'][side]
    total['groups'] += 1
    total['book'].update(part['book'])
    total['events'].update({k: v for k, v in part['events'].items()})
    for measure, found in part['differs'].items():
        total['reasons'][measure].update(found['reasons'])
    total['incomplete'].update(part['incomplete'])
    total['listing'].update(result['listing'])
    return total


def copy(total):
    return dict(book=Counter(total['book']), events=Counter(total['events']),
                reasons={m: Counter(c) for m, c in total['reasons'].items()}, incomplete=Counter(total['incomplete']),
                listing=Counter(total['listing']), groups=total['groups'], not_read=total['not_read'])


def columns(total):
    """The window's book counterparts of the pinned balance and absorption (value dicts with their incomplete listing),
    the counts both ways and the reconciliation."""
    from .c15_teacher import value
    from .c15_normalizer import State
    listed = Counter(total['listing'])
    if total['not_read']:
        listed['GROUP_NOT_READ'] += total['not_read']
    listed = dict(sorted(listed.items()))
    book, events = total['book'], total['events']

    def carried(v):
        return dict(v, incomplete=listed) if listed else v
    if not total['groups']:
        balance = absorption = carried(value(state=State.MISSING, reason='NO_GROUP_READ'))
    else:
        balance = carried(value(math.log1p(book['added']) - math.log1p(book['removed'])))
        absorption = carried(value(book['fills'] / book['removed']) if book['removed'] else
                             value(state=State.MISSING, reason='NO_REMOVALS'))
    reconciliation = {m: dict(book=book[m], events=events[m], equal=book[m] == events[m],
                              reasons=dict(sorted(total['reasons'][m].items())))
                      for m in MEASURES}
    return dict(book_balance=balance, book_absorption=absorption,
                counts=dict(book=dict(sorted(book.items())), events=dict(sorted(events.items())),
                            groups=total['groups'], groups_not_read=total['not_read']),
                event_incomplete=dict(sorted(total['incomplete'].items())), reconciliation=reconciliation)


# ---- the per-state split (Greg, 2026-10-09: the pinned measures split by the bedrock state present at that moment).
# A split, not a new formula: each group's own parts (the event-derived counts the pinned functions sum: added,
# removed, modifies, priority lost, fills and the absorption's removed quantity, plus the book counts) go to the bucket
# of the label its closing instant carries, for every label field separately; every field's buckets sum back to the
# window's totals (recorded per row). A group whose closing instant carries no row of that plane goes to
# STATE_UNKNOWN, never dropped. Bucket keys are the labels' own values, JSON-encoded (a tuple of several rows' values
# as a list); nothing is renamed or binned. The dipole state is the teacher row's own DState (teacher.dstate|...).
SPLIT_FORMAT = 1
STATE_UNKNOWN = '__state_unknown__'
EVENT_PARTS = ('added', 'removed', 'modifies', 'lost', 'fills', 'absorption_removed')
BOOK_PARTS = ('added', 'removed', 'modifies', 'fills')


def label_key(value):
    import json
    return json.dumps(value, sort_keys=True, default=repr)


def state_split(results, labels, side):
    """The split of one window on `side`: results and labels are the window's groups in order (a result None: the group
    was not read; it is counted apart, in no bucket and not in the totals)."""
    fields = sorted({name for label in labels if label for name in label})
    totals = dict(groups=0, events=Counter(), book=Counter())
    not_read = 0
    split = {}
    for result, label in zip(results, labels):
        if result is None:
            not_read += 1
            continue
        part = result['sides'][side]
        totals['groups'] += 1
        totals['events'].update({k: part['events'][k] for k in EVENT_PARTS})
        totals['book'].update({k: part['book'][k] for k in BOOK_PARTS})
        for name in fields:
            key = label_key(label[name]) if label and name in label else STATE_UNKNOWN
            bucket = split.setdefault(name, {}).setdefault(key, dict(groups=0, events=Counter(), book=Counter()))
            bucket['groups'] += 1
            bucket['events'].update({k: part['events'][k] for k in EVENT_PARTS})
            bucket['book'].update({k: part['book'][k] for k in BOOK_PARTS})
    out = {}
    for name, buckets in split.items():
        events, book, groups = Counter(), Counter(), 0
        for bucket in buckets.values():
            events.update(bucket['events'])
            book.update(bucket['book'])
            groups += bucket['groups']
        sums_back = (events == totals['events'] and book == totals['book'] and groups == totals['groups'])
        out[name] = dict(buckets={key: dict(groups=b['groups'], events=dict(sorted(b['events'].items())),
                                            book=dict(sorted(b['book'].items())))
                                  for key, b in sorted(buckets.items())},
                         unknown_groups=buckets.get(STATE_UNKNOWN, {}).get('groups', 0), sums_back=sums_back)
    return dict(format=SPLIT_FORMAT, side=side, totals=dict(groups=totals['groups'],
                                                            events=dict(sorted(totals['events'].items())),
                                                            book=dict(sorted(totals['book'].items()))),
                groups_not_read=not_read, fields=out,
                all_sum_back=all(field['sums_back'] for field in out.values()),
                unknown_rule='a group whose closing instant carries no row of that plane: %s' % STATE_UNKNOWN)


def pinned_check(split, combined, length):
    """The pinned short-window values recomputed from the split's totals with the pinned arithmetic (control dynamics
    balance and priority-loss rate, R3 absorption share): equal, or listed with the reason."""
    from .c15_teacher import value
    from .c15_normalizer import State
    events = split['totals']['events']
    if not split['totals']['groups']:
        return dict(status='no group read')
    if length != 64:
        return dict(status='not compared', reason='the window holds %d groups; the pinned 64-group windows of the '
                                                  'first groups differ (the absorption reads groups[-64:])' % length)
    added, removed = events.get('added', 0), events.get('removed', 0)
    modifies, lost = events.get('modifies', 0), events.get('lost', 0)
    fills, absorbed = events.get('fills', 0), events.get('absorption_removed', 0)
    recomputed = dict(
        control_balance_64=value(math.log1p(added) - math.log1p(removed)),
        control_priority_loss_64=value(lost / modifies) if modifies else value(state=State.MISSING, reason='NO_MODIFIES'),
        r3_absorption_64=value(fills / absorbed) if absorbed else value(state=State.MISSING, reason='NO_REMOVALS'))
    columns = dict(control_balance_64=3, control_priority_loss_64=5, r3_absorption_64=7)
    out = {}
    for name, index in columns.items():
        pinned = combined[index] if index < len(combined) else None
        mine = recomputed[name]
        equal = (isinstance(pinned, dict) and pinned.get('state') == mine['state']
                 and pinned.get('value') == mine['value'])
        out[name] = dict(pinned=None if pinned is None else dict(value=pinned.get('value'), state=pinned.get('state'),
                                                                 reason=pinned.get('reason')),
                         from_parts=mine, equal=equal)
    return dict(status='compared', columns=out, all_equal=all(item['equal'] for item in out.values()))


def window(results, side):
    total = _empty()
    for result in results:
        add(total, result, side)
    return columns(total)


def assemble(rows, cursor_group, groups, windows, *, whole_day, group_labels=None):
    """Per teacher row (in order), its book read: the group it closes (receipt rows) and each window the pinned R3
    called on it (slot -> (key, end ordinal, length, side)); `whole_day` adds the whole-day running window on the
    short window's side (the teacher changes' long horizon). A row that closes no group reads NOT_F_LAST and a receipt
    row with no window the pinned R3's own reason (its R3 column), exactly as the pinned columns do."""
    from .c15_teacher import value
    from .c15_normalizer import State
    running = {}
    out = []
    for row in rows:
        cursor, has_receipt, combined = row[6], row[1], row[3]
        if not has_receipt:
            out.append(dict(status='NOT_F_LAST', columns=value(state=State.MISSING, reason='NOT_F_LAST')))
            continue
        key, ordinal = cursor_group.get(cursor, (None, None))
        result = groups.get((key, ordinal)) if key is not None else None
        entry = dict(status='GROUP' if result is not None else 'GROUP_NOT_READ', key=key, ordinal=ordinal, group=result)
        slots = windows.get(cursor) or {}
        reads = {}
        for slot, (wkey, end, length, side) in sorted(slots.items()):
            ordinals = range(end - length + 1, end + 1)
            results = [groups.get((wkey, o)) for o in ordinals]
            reads[slot] = dict(side=side, length=length, **window(results, side))
            if group_labels is not None:
                split = state_split(results, [group_labels.get((wkey, o)) for o in ordinals], side)
                split['pinned_check'] = pinned_check(split, combined, length) if slot == 'short' else dict(
                    status='not compared', reason='the pinned long horizon is the running whole-day total')
                reads[slot]['state_split'] = split
        if whole_day and 'short' in slots and key is not None:
            wkey, end, _, side = slots['short']
            held = running.setdefault(wkey, dict(upto=-1, totals={s: _empty() for s in SIDES}))
            while held['upto'] < end:
                held['upto'] += 1
                for s in SIDES:
                    add(held['totals'][s], groups.get((wkey, held['upto'])), s)
            reads['day'] = dict(side=side, length=end + 1, **columns(held['totals'][side]))
        if not slots:
            reason = combined[7].get('reason') if len(combined) > 7 and isinstance(combined[7], dict) else None
            entry['windows_absent'] = reason or 'no window'
        entry['windows'] = reads
        out.append(entry)
    return out
