"""Full-session mechanism inventory and cross-date rolling-flow discovery.

Uses pinned raw messages and retained groups/tables. No producer or simulator run.
"""
from collections import Counter
from dataclasses import dataclass
import gzip
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from flow_book_discovery import GROUPS, REV, NS, rows, blob

HERE = Path(__file__).resolve().parent
OUT = HERE / 'research-atlas-v2'
TAPE_REV = '1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202'
OPEN = 1697580000 * NS
CLOSE = 1697662800 * NS


def save(name, data):
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    opts = {'compression': {'method': 'gzip', 'mtime': 0}} if name.endswith('.gz') else {}
    frame.to_csv(OUT / name, index=False, **opts)


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


@dataclass
class RestingOrder:
    side: str
    price: int
    displayed: int
    fills: int = 0
    pending: int = 0
    matched_reductions: int = 0
    unlinked_reductions: int = 0
    implied_additions: int = 0
    unmatched_fill_at_boundary: int = 0

    def update(self, action, side, price, size):
        if action == 'F':
            if side == self.side and price == self.price:
                self.fills += size
                self.pending += size
            return None
        if action not in ('M', 'C', 'A'):
            return None
        if action == 'A':
            return 'duplicate_add_unresolved'
        if action == 'M' and (side != self.side or price != self.price):
            return 'reprice'
        after = max(0, self.displayed - size) if action == 'C' else size
        reduction = max(0, self.displayed - after)
        matched = min(self.pending, reduction)
        self.matched_reductions += matched
        self.unlinked_reductions += reduction - matched
        # This accounting describes display implied by observed F and mutation,
        # without asserting reserve size, a trader motive, or extra executions.
        if action == 'M':
            self.implied_additions += max(0, after - self.displayed + self.pending)
            self.pending = 0
        else:
            self.pending -= matched
        self.displayed = after
        if after == 0:
            if reduction and matched == reduction:
                return 'fill_linked_clear'
            return 'mixed_clear' if matched else 'unmatched_clear'
        return None

    def boundary(self):
        self.unmatched_fill_at_boundary += self.pending
        self.pending = 0


def rolling_flow(buy, sell, window=20):
    def roll(a):
        c = np.r_[0., np.cumsum(a)]
        return c[1:] - c[np.maximum(0, np.arange(len(a)) + 1 - window)]
    b, s = roll(buy), roll(sell)
    total = b + s
    r = np.divide(b - s, total, out=np.full(len(total), np.nan), where=total > 0)
    state = np.where(np.isnan(r), 2, np.sign(np.nan_to_num(r))).astype(int)
    change = np.r_[False, np.isfinite(r[1:]) & np.isfinite(r[:-1]) & (np.abs(np.diff(r)) > 1e-12)]
    warm = np.arange(len(total)) >= window
    flip = np.r_[False, (state[1:] * state[:-1] == -1)] & warm
    return dict(roll_buy=b, roll_sell=s, total=total, ratio=r, state=state,
                ratio_change=change & warm, age_only_change=change & (buy + sell == 0) & warm,
                direction_flip=flip, age_only_flip=flip & (buy + sell == 0), warm=warm)


def cross_date_flow(groups):
    flow_days = {}
    for day in ('20231002', '20231017'):
        base = HERE / 'flow-book-discovery-v1/date-tables' / day
        with gzip.open(base / 'legacy_native_signed_flow.json.gz', 'rt') as f:
            source = json.load(f)
        per = source['per_second']
        seconds = np.array([r['second'] for r in per], dtype=np.int64)
        if not np.all(np.diff(seconds) == 1):
            raise ValueError('per-second source contains a gap')
        flow_days[day] = (seconds, np.array([r['buy'] for r in per]), np.array([r['sell'] for r in per]))
    seconds = np.arange(OPEN // NS, CLOSE // NS, dtype=np.int64)
    buy, sell = np.zeros(len(seconds)), np.zeros(len(seconds))
    classified = Counter()
    previous = None
    for g in groups:
        for t in g['prints']:
            if not (OPEN <= t['receive_ns'] < CLOSE) or not previous or not previous['bid'] or not previous['ask']:
                continue
            ix = t['receive_ns'] // NS - seconds[0]
            delta = 2 * t['price_raw'] - previous['bid'][0] - previous['ask'][0]
            side = 'buy' if delta > 0 else 'sell' if delta < 0 else 'at_mid'
            classified[side + '_prints'] += 1
            if delta:
                (buy if delta > 0 else sell)[ix] += t['size']
        if g['bid'] and g['ask'] and not any(g[k] for k in ('reset_member', 'snapshot_member', 'bad_receive_clock_member')):
            previous = g
    flow_days['20231018'] = (seconds, buy, sell)
    summaries, transitions, all_seconds = [], [], []
    for day, (seconds, buy, sell) in flow_days.items():
        f = rolling_flow(buy, sell)
        finite = f['warm'] & np.isfinite(f['ratio'])
        known = finite.sum()
        summary = dict(day=day, tape_scope='full_session' if day == '20231018' else 'partial',
                       seconds=len(seconds), first_second=int(seconds[0]), last_second=int(seconds[-1]),
                       warm_seconds=int(f['warm'].sum()), defined_warm_seconds=int(known),
                       ratio_changes=int(f['ratio_change'].sum()), age_only_ratio_changes=int(f['age_only_change'].sum()),
                       direction_flips=int(f['direction_flip'].sum()), age_only_direction_flips=int(f['age_only_flip'].sum()),
                       one_lot_saturated_seconds=int((finite & (f['total'] == 1) & (np.abs(f['ratio']) == 1)).sum()),
                       saturated_seconds=int((finite & (np.abs(f['ratio']) == 1)).sum()),
                       buy_lots=float(buy.sum()), sell_lots=float(sell.sum()))
        summaries.append(summary)
        for before in (-1, 0, 1, 2):
            for after in (-1, 0, 1, 2):
                mask = (f['state'][:-1] == before) & (f['state'][1:] == after) & f['warm'][1:]
                transitions.append(dict(day=day, before=before, after=after, n=int(mask.sum()),
                                        no_fresh_classified_lots=int((mask & (buy[1:] + sell[1:] == 0)).sum())))
        frame = pd.DataFrame(dict(day=day, second=seconds, buy=buy, sell=sell, **f))
        all_seconds.append(frame)
    save('rolling-flow-seconds.csv.gz', pd.concat(all_seconds, ignore_index=True))
    save('rolling-flow-date-summary.csv', summaries)
    save('rolling-flow-state-transitions.csv', transitions)
    dump('flow-method.json', dict(window_seconds=20, warmup_excluded_first_seconds=20,
                                  classified_oct18_prints=dict(classified), state_labels={'-1':'sell','0':'balanced','1':'buy','2':'undefined'},
                                  source_oct18=REV + ':' + GROUPS, source_oct2_oct17='f0bd88e1728668ae3fc9bdd5f62921f9d89fcd13 retained ROOT arrays',
                                  limitations=['Receive-second bins are descriptive, not the actual delayed emission clock.',
                                               'The three date spans differ; seconds overlap in rolling windows and are not independent trials.',
                                               'October 3 is pending; no fourth-date comparison is imputed.',
                                               'Aging-only means no fresh classified lots; midpoint/unknown prints may still exist.']))


def group_matrix(groups):
    result, segment = [], 0
    for g in groups:
        good = (OPEN <= g['receive_ns'] < CLOSE and g['bid'] and g['ask'] and
                0 < g['bid'][0] < g['ask'][0] and not any(g[k] for k in ('reset_member', 'snapshot_member', 'bad_receive_clock_member')))
        if not good:
            segment += 1
        b, a = g['bid'] or [0, 0, 0], g['ask'] or [0, 0, 0]
        result.append((g['receive_ns'], g['close_cursor'], b[0] + a[0], b[0], a[0], b[1], a[1], int(bool(good)), segment))
    return np.array(result, dtype=np.int64)


def raw_records():
    import databento as db
    for day, offset in (('20231017', -841601), ('20231018', 17375)):
        path = f'data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{day}.dbn.zst'
        raw = subprocess.check_output(['git', 'show', f'{TAPE_REV}:{path}'])
        for index, r in enumerate(db.DBNStore.from_bytes(raw)):
            cursor = index + offset
            if cursor >= 0:
                yield cursor, r, day, index


def mechanism_inventory(groups, a):
    active, events, action_rows, anchors = {}, [], [], []
    pending = {}
    gi = 0
    trade_groups, residual_groups = set(), set()
    processed = 0

    def finish(oid, state, kind, cursor, recv, group):
        event, tracker = state
        event.update(end_kind=kind, end_cursor=cursor, end_receive_ns=recv, end_group=group,
                     end_known_by_ns=int(a[group, 0]), total_passive_fill_lots=tracker.fills,
                     matched_display_reductions=tracker.matched_reductions,
                     unlinked_display_reductions=tracker.unlinked_reductions,
                     implied_added_display=tracker.implied_additions,
                     unmatched_fills_at_group_boundary=tracker.unmatched_fill_at_boundary + tracker.pending,
                     final_display=tracker.displayed)
        active.pop(oid, None)

    for cursor, r, day, raw_index in raw_records():
        if cursor > int(a[-1, 1]):
            break
        while cursor > a[gi, 1]:
            for event, tracker in active.values():
                if event['start_group'] == gi:
                    event['size_at_start_close'] = tracker.displayed
                tracker.boundary()
            pending.clear()
            gi += 1
        processed += 1
        oid, action, side = int(r.order_id), str(r.action), str(r.side)
        price, size, recv = int(r.price), int(r.size), int(r.ts_recv)
        if action == 'T' and a[gi, 7]:
            trade_groups.add(gi)
            if oid and side in ('A', 'B'):
                p = pending.setdefault(oid, dict(side=side, qty=0, prices=set(), first_cursor=cursor, first_ns=recv))
                p['qty'] += size
                p['prices'].add(price)
        if oid in active and action in ('F', 'M', 'C', 'A'):
            state = active[oid]
            ending = state[1].update(action, side, price, size)
            action_rows.append(dict(event_id=state[0]['event_id'], cursor=cursor, receive_ns=recv, group=gi,
                                    group_known_by_ns=int(a[gi, 0]), action=action, side=side, price_raw=price,
                                    size=size, order_id=oid, displayed_after=state[1].displayed,
                                    cumulative_passive_fills=state[1].fills, raw_day=day, raw_record_index=raw_index))
            if ending:
                finish(oid, state, ending, cursor, recv, gi)
        if action == 'R':
            for existing, state in list(active.items()):
                finish(existing, state, 'reset_censored', cursor, recv, gi)
        p = pending.get(oid)
        if action == 'A' and p and size > 0 and p['side'] == side and a[gi, 7]:
            event = dict(event_id=f'rest-{cursor}-{oid}', order_id=oid, side=side,
                         direction=1 if side == 'B' else -1, initial_display=size, resting_price_raw=price,
                         initial_trade_lots=p['qty'], initial_trade_price_count=len(p['prices']),
                         first_trade_cursor=p['first_cursor'], first_trade_receive_ns=p['first_ns'],
                         add_cursor=cursor, add_receive_ns=recv, start_group=gi, start_close_cursor=int(a[gi, 1]),
                         start_known_by_ns=int(a[gi, 0]), size_at_start_close=0,
                         raw_day=day, raw_record_index=raw_index)
            events.append(event)
            active[oid] = (event, RestingOrder(side, price, size))
            residual_groups.add(gi)
            pending.pop(oid)
    # EOF closes the final retained group, just as advancing the cursor closes
    # earlier groups. An add in that last group is visible at its close.
    for event, tracker in active.values():
        if event['start_group'] == gi:
            event['size_at_start_close'] = tracker.displayed
        tracker.boundary()
    for oid, state in list(active.items()):
        finish(oid, state, 'session_end_censored', int(a[-1, 1]), int(a[-1, 0]), len(a) - 1)
    # A remainder that ended within its initial group never became standing
    # liquidity in a completed-group decision. Keep it, with size zero there.
    for e in events:
        e['duration_from_start_close_ns'] = e['end_known_by_ns'] - e['start_known_by_ns']
        e['visible_at_start_close'] = e['size_at_start_close'] > 0
        for anchor, group in (('start_close', e['start_group']), ('end_close', e['end_group'])):
            if anchor == 'end_close' and e['end_kind'].endswith('censored'):
                continue
            for h in (1, 5, 20, 60, 300):
                t = int(a[group, 0]) + h * NS
                end = int(np.searchsorted(a[:, 0], t, side='right')) - 1
                valid = t <= int(a[-1, 0]) and a[group, 7] and a[end, 7] and a[group, 8] == a[end, 8]
                change = (int(a[end, 2]) - int(a[group, 2])) / (2 * NS)
                anchors.append(dict(event_id=e['event_id'], anchor=anchor, group=group, known_by_ns=int(a[group, 0]),
                                    horizon_s=h, target_ns=t, endpoint_group=end, endpoint_cursor=int(a[end, 1]),
                                    endpoint_receive_ns=int(a[end, 0]), endpoint_age_ns=t-int(a[end, 0]),
                                    disposition='available' if valid else 'censored_or_boundary',
                                    change=change if valid else None, direction_oriented_change=change*e['direction'] if valid else None,
                                    change_pct=100 * change / (a[group, 2]/(2*NS)) if valid else None))
    save('aggression-to-rest-events.csv', events)
    save('aggression-to-rest-actions.csv.gz', action_rows)
    save('aggression-to-rest-outcomes.csv.gz', anchors)
    dump('mechanism-method.json', dict(version='NG-AGGRESSION-TO-REST-v1', source_tape_revision=TAPE_REV,
                                       source_groups_revision=REV, raw_records_processed=processed,
                                       print_groups=len(trade_groups), residual_groups=len(residual_groups), events=len(events),
                                       definition='Same nonzero order ID and wire side on T then A within the same completed group; follow the new resting display until removal, reprice, reset or session end.',
                                       boundaries=['The match is order identity, not participant identity or private intent.',
                                                   'T summaries and F passive fills remain separate quantities.',
                                                   'Final removal mechanism is a later outcome, never a birth predictor.',
                                                   'Unmatched removal means no matched passive F in the tracked group; it is not proof of discretionary cancellation.',
                                                   'Implied display additions are accounting from F plus mutation; reserve quantity is unobserved.',
                                                   'All events retained, including those gone before the initial group close.']))
    return pd.DataFrame(events), pd.DataFrame(anchors)


def summarize_mechanisms(events, outcomes):
    merged = outcomes.merge(events, on='event_id', validate='many_to_one', suffixes=('', '_event'))
    summary = []
    for (anchor, h, side, kind), g in merged.groupby(['anchor', 'horizon_s', 'side', 'end_kind']):
        v = g[g.disposition.eq('available')].direction_oriented_change
        summary.append(dict(anchor=anchor, horizon_s=h, side=side, eventual_end_kind=kind,
                            n=len(g), available=len(v), continuation=int((v>0).sum()), reversal=int((v<0).sum()),
                            flat=int((v==0).sum()), mean=v.mean(), median=v.median(), q10=v.quantile(.1), q90=v.quantile(.9)))
    save('mechanism-outcome-summary.csv', summary)
    cases = pd.read_csv(HERE/'flow-book-discovery-v1/opportunities.csv.gz', dtype={'anchor_ns':str})
    links = []
    for case in cases.itertuples():
        t = int(case.anchor_ns)
        for e in events[(events.start_known_by_ns <= t+5*NS) & (events.end_known_by_ns >= t-NS)].itertuples():
            links.append(dict(instance=case.instance, event_id=e.event_id, cohort=case.cohort,
                              family_anchor_ns=t, start_known_by_ns=e.start_known_by_ns, end_known_by_ns=e.end_known_by_ns,
                              relative_start_ns=e.start_known_by_ns-t,
                              available_by_prior_book=e.start_known_by_ns<=int(case.pre_receive_ns),
                              relation='overlap_-1s_+5s_not_independent_confirmation'))
    save('family-to-resting-events.csv', links)


def main():
    OUT.mkdir(exist_ok=True)
    groups = rows(GROUPS)
    cross_date_flow(groups)
    a = group_matrix(groups)
    events, outcomes = mechanism_inventory(groups, a)
    summarize_mechanisms(events, outcomes)
    print(events.groupby(['side','end_kind']).size().to_string())


if __name__ == '__main__':
    main()
