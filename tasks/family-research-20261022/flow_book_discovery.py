"""Four-arm October discovery on retained tables; never a simulator or scoring rule.

Run from a Markets checkout. All inputs are immutable Git blobs; no producer runs.
"""
import csv
import argparse
import gzip
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

REV = 'b5f28bd57de5ed4ff889335edb9a33216b67eb6a'
BASE = 'artifacts/sqlite-triage/20261022/families/'
REVIEW = BASE + 'instance-market-review-20261023/'
GROUPS = ('research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/'
          'root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz')
HERE = Path(__file__).resolve().parent
OUT = HERE / 'flow-book-discovery-v1'
NS = 1_000_000_000
HORIZONS = (1, 5, 20, 60, 300)


def blob(path):
    return subprocess.check_output(['git', 'show', f'{REV}:{path}'])


def rows(path):
    raw = blob(path)
    if path.endswith('.gz'):
        raw = gzip.decompress(raw)
    stream = io.StringIO(raw.decode())
    return list(map(json.loads, stream)) if '.jsonl' in path else list(csv.DictReader(stream))


def save(name, data):
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    args = {'compression': {'method': 'gzip', 'mtime': 0}} if name.endswith('.gz') else {}
    frame.to_csv(OUT / name, index=False, **args)


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def asof_index(times, cursors, cutoff, cap):
    return min(int(np.searchsorted(times, cutoff, side='right')) - 1,
               int(np.searchsorted(cursors, cap, side='right')) - 1)


def ratio(buy, sell):
    return (buy - sell) / (buy + sell) if buy + sell > 0 else None


def stack_class(f1, f5, f60, depth):
    if any(v is None or not np.isfinite(v) for v in (f1, f5, f60, depth)):
        return 'missing'
    if f1 < 0 and f5 < 0 and f60 > 0 and depth > 0:
        return 'original'
    if f1 > 0 and f5 > 0 and f60 < 0 and depth < 0:
        return 'inverse'
    return 'other'


def purged_training(times, test_start, horizon_ns):
    return np.flatnonzero(times[:test_start] + horizon_ns < times[test_start])


def load_groups():
    # Keep the integer clocks and raw half-tick midpoint numerator exact.
    raw = rows(GROUPS)
    result, segment = [], 0
    for g in raw:
        bid, ask = g['bid'], g['ask']
        good = (bid is not None and ask is not None and 0 < bid[0] <= ask[0]
                and not any(g[k] for k in ('snapshot_member', 'reset_member', 'bad_receive_clock_member')))
        if not good:
            segment += 1
        result.append((g['receive_ns'], g['close_cursor'], g['group_ordinal'], g['first_cursor'],
                       bid[0] if bid else 0, ask[0] if ask else 0,
                       bid[1] if bid else 0, ask[1] if ask else 0, int(good), segment))
    a = np.asarray(result, dtype=np.int64)
    if np.any(np.diff(a[:, 0]) < 0) or np.any(np.diff(a[:, 1]) <= 0):
        raise ValueError('group ordering is unsuitable for as-of joins')
    return a


def opportunities(a):
    index = rows(REVIEW + 'chronological-instance-index.csv')
    result, outcomes = [], []
    times, cursors = a[:, 0], a[:, 1]
    for source in index:
        t, cap = int(source['start_recv_ns']), int(source['cursor_cap'])
        j = asof_index(times, cursors, t - 1, cap)
        r = {k: source[k] for k in ('instance', 'sample_id', 'family_id', 'start_utc')}
        r.update(anchor_ns=t, cutoff_ns=t - 1, cursor_cap=cap)
        # All root.* operands are strict-pre saved measurements, with original refs retained.
        for k, v in source.items():
            if k.startswith('root.'):
                r[k] = float(v) if v else np.nan
        for h in (1, 5, 60):
            b, s = (r[f'root.activity.{h}.trade_{side}_aggressor_qty'] for side in ('buy', 'sell'))
            r[f'flow{h}'] = ratio(b, s)
            r[f'activity{h}'] = np.log1p(b + s)
        r['cohort'] = stack_class(r['flow1'], r['flow5'], r['flow60'], r['root.depth_imbalance_full'])
        r['input_disposition'] = 'available'
        if j < 0 or not a[j, 8]:
            r['input_disposition'] = 'no_eligible_prequote'
            result.append(r)
            continue
        g = a[j]
        if int(source['pre_source_ordinal']) != g[2] or int(source['pre_input_cursor']) != g[1]:
            raise ValueError(f'saved prequote mismatch for {r["instance"]}')
        r.update(pre_group=int(g[2]), pre_cursor=int(g[1]), pre_receive_ns=int(g[0]),
                 pre_age_ns=t - 1 - int(g[0]), mid=(g[4] + g[5]) / (2 * NS),
                 spread=(g[5] - g[4]) / NS, touch_bid=int(g[6]), touch_ask=int(g[7]),
                 touch_imbalance=ratio(g[6], g[7]), touch_size_log=np.log1p(g[6] + g[7]))
        for lag in (1, 5):
            k = asof_index(times, cursors, t - lag * NS - 1, cap)
            if k < 0 or not a[k, 8] or a[k, 9] != g[9]:
                r['input_disposition'] = 'missing_or_cross_boundary_lookback'
                continue
            p = a[k]
            r.update({f'lag{lag}_group': int(p[2]), f'lag{lag}_cursor': int(p[1]),
                      f'lag{lag}_receive_ns': int(p[0]),
                      f'prior_mid{lag}': (g[4] + g[5] - p[4] - p[5]) / (2 * NS),
                      f'touch_delta{lag}': ratio(g[6], g[7]) - ratio(p[6], p[7]),
                      f'bid_same_price{lag}': int(g[4] == p[4]),
                      f'ask_same_price{lag}': int(g[5] == p[5]),
                      f'bid_display_change{lag}': int(g[6] - p[6]) if g[4] == p[4] else 0,
                      f'ask_display_change{lag}': int(g[7] - p[7]) if g[5] == p[5] else 0})
        result.append(r)
        for h in HORIZONS:
            target = t + h * NS
            k = asof_index(times, cursors, target, int(cursors[-1]))
            p = a[k]
            valid = target <= times[-1] and p[8] and p[9] == g[9]
            move = (int(p[4]) + int(p[5]) - int(g[4]) - int(g[5])) / (2 * NS)
            outcomes.append(dict(instance=r['instance'], horizon_s=h, target_ns=target,
                                 outcome_disposition='available' if valid else 'censored_or_boundary',
                                 endpoint_group=int(p[2]), endpoint_cursor=int(p[1]), endpoint_receive_ns=int(p[0]),
                                 endpoint_age_ns=target - int(p[0]), change=move if valid else None,
                                 change_pct=100 * move / r['mid'] if valid else None,
                                 change_ticks=move / .001 if valid else None))
    frame = pd.DataFrame(result)
    # Retain nullable coordinates as decimal strings, never float-rounded clocks.
    for key in frame:
        if key.endswith(('_ns', '_cursor', '_group')):
            frame[key] = [str(r[key]) if key in r else '' for r in result]
    return frame, pd.DataFrame(outcomes)


BASELINE = ['spread', 'activity1', 'activity60', 'prior_mid1', 'prior_mid5']
FLOW = ['flow1', 'flow5', 'flow60']
BOOK = ['touch_imbalance', 'touch_size_log', 'touch_delta1', 'touch_delta5',
        'root.depth_imbalance_n', 'root.depth_imbalance_full',
        'bid_same_price1', 'ask_same_price1', 'bid_display_change1', 'ask_display_change1',
        'bid_same_price5', 'ask_same_price5', 'bid_display_change5', 'ask_display_change5']
ARMS = {'baseline': BASELINE, 'flow': BASELINE + FLOW,
        'book': BASELINE + BOOK, 'both': BASELINE + FLOW + BOOK}


def fit_arms(frame, outcomes, embargo_s=600):
    predictions, metrics, splits = [], [], []
    all_inputs = list(dict.fromkeys(BASELINE + FLOW + BOOK))
    complete = frame.input_disposition.eq('available') & np.isfinite(frame[all_inputs].astype(float)).all(axis=1)
    frame['four_arm_eligible'] = complete
    for h in HORIZONS:
        x = frame.loc[complete].merge(outcomes[outcomes.horizon_s.eq(h)], on='instance', validate='one_to_one')
        x = x[x.outcome_disposition.eq('available')].reset_index(drop=True)
        times = x.anchor_ns.map(int).to_numpy(dtype=np.int64)
        for fold, (lo, hi) in enumerate(((.4, .6), (.6, .8), (.8, 1.)), 1):
            start, stop = int(len(x) * lo), int(len(x) * hi)
            train = purged_training(times, start, (h + embargo_s) * NS)
            test = np.arange(start, stop)
            splits.append(dict(horizon_s=h, fold=fold, embargo_s=embargo_s, eligible=len(x), n_train=len(train), n_test=len(test),
                               test_start_ns=int(times[start]), last_train_label_target_ns=int(times[train[-1]] + h * NS),
                               train_instances=';'.join(x.iloc[train].instance), test_instances=';'.join(x.iloc[test].instance)))
            for target in ('signed', 'absolute'):
                y = x.change.to_numpy() if target == 'signed' else np.abs(x.change.to_numpy())
                for arm, columns in ARMS.items():
                    matrix = x[columns].to_numpy(dtype=float)
                    mean, scale = matrix[train].mean(axis=0), matrix[train].std(axis=0)
                    scale[scale < 1e-12] = 1
                    z = (matrix - mean) / scale
                    ym = y[train].mean()
                    coef = np.linalg.solve(z[train].T @ z[train] + 10 * np.eye(len(columns)),
                                           z[train].T @ (y[train] - ym))
                    pred = ym + z[test] @ coef
                    err = np.abs(pred - y[test])
                    metrics.append(dict(horizon_s=h, target=target, fold=fold, arm=arm,
                                        n_train=len(train), n_test=len(test), mae=float(err.mean()),
                                        negative_magnitude_predictions=int((pred < 0).sum()) if target == 'absolute' else 0,
                                        direction_agreements=int((np.sign(pred) == np.sign(y[test])).sum()) if target == 'signed' else None))
                    for k, value, loss in zip(test, pred, err):
                        predictions.append(dict(instance=x.at[k, 'instance'], horizon_s=h, target=target,
                                                fold=fold, arm=arm, observed=float(y[k]), prediction=float(value), absolute_error=float(loss)))
    save('arm-predictions.csv.gz', predictions)
    save('arm-metrics.csv', metrics)
    save('chronological-splits.csv', splits)
    return pd.DataFrame(metrics)


def cohort_tables(frame, outcomes):
    joined = frame.merge(outcomes, on='instance', validate='one_to_many')
    records = []
    for h in HORIZONS:
        sub = joined[joined.horizon_s.eq(h)]
        for name, mask in [('all', np.ones(len(sub), dtype=bool))] + [(c, sub.cohort.eq(c)) for c in ('original', 'inverse', 'other', 'missing')]:
            g = sub.loc[mask]
            good = g[g.outcome_disposition.eq('available')]
            intervals = sorted((int(r.anchor_ns), int(r.target_ns)) for r in good.itertuples())
            clusters, end = 0, -1
            for start, stop in intervals:
                if start > end:
                    clusters += 1
                end = max(end, stop)
            moves = good.change
            records.append(dict(horizon_s=h, cohort=name, n=len(g), available=len(good), interval_clusters=clusters,
                                down=int((moves < 0).sum()), flat=int((moves == 0).sum()), up=int((moves > 0).sum()),
                                mean=moves.mean(), q10=moves.quantile(.1), median=moves.median(), q90=moves.quantile(.9)))
    save('cohort-outcomes.csv', records)
    # Descriptive controls: same UTC hour and rounded spread; nearest 60s classified
    # lot count on a log scale, then smallest clock distance. Selection uses no outcome.
    controls = []
    for cohort in ('original', 'inverse'):
        for r in frame[frame.cohort.eq(cohort)].to_dict('records'):
            pool = frame[(frame.cohort == 'other') & frame.input_disposition.eq('available')].copy()
            pool = pool[(pool.anchor_ns.map(int) // (3600 * NS) == int(r['anchor_ns']) // (3600 * NS))
                        & np.isclose(pool.spread, r['spread'])]
            if pool.empty:
                controls.append(dict(instance=r['instance'], cohort=cohort, disposition='no_same_hour_spread_control'))
                continue
            pool['activity_distance'] = abs(pool.activity60 - r['activity60'])
            pool['clock_distance_ns'] = abs(pool.anchor_ns.map(int) - int(r['anchor_ns']))
            other = pool.sort_values(['activity_distance', 'clock_distance_ns']).iloc[0]
            controls.append(dict(instance=r['instance'], cohort=cohort, control_instance=other.instance,
                                 disposition='matched_with_replacement', activity_log_distance=other.activity_distance,
                                 clock_distance_ns=str(int(other.clock_distance_ns))))
    save('activity-controls.csv', controls)
    deltas = []
    lookup = outcomes.set_index(['instance', 'horizon_s'])
    for r in controls:
        if 'control_instance' not in r:
            continue
        for h in HORIZONS:
            left, right = lookup.loc[r['instance'], h], lookup.loc[r['control_instance'], h]
            if left.outcome_disposition == right.outcome_disposition == 'available':
                deltas.append(dict(**r, horizon_s=h, case_change=left.change, control_change=right.change,
                                   paired_change_difference=left.change - right.change))
    save('activity-control-outcomes.csv', deltas)


def dipole_followup(a):
    candidates = rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz')
    result = []
    for c in candidates:
        t = c['recognition_receive_ns']
        j = asof_index(a[:, 0], a[:, 1], t, c['recognition_cursor'])
        g = a[j]
        assert g[0] == t and g[2] == c['recognition_group']
        for h in HORIZONS:
            target = t + h * NS
            k = asof_index(a[:, 0], a[:, 1], target, int(a[-1, 1]))
            p = a[k]
            valid = target <= a[-1, 0] and g[8] and p[8] and p[9] == g[9]
            flow = c['last_closed_window'].get('roll20')
            result.append(dict(candidate_id=c['candidate_id'], birth_second=c['birth_second'],
                               recognition_ns=t, recognition_cursor=c['recognition_cursor'], recognition_group=c['recognition_group'],
                               birth_polarity=c['recorded_operands']['polarity'], recognition_roll20=flow,
                               recognition_classified_lots=c['last_closed_window']['classified_lots'],
                               recognition_buy_lots=c['last_closed_window'].get('buy_lots', 0),
                               recognition_sell_lots=c['last_closed_window'].get('sell_lots', 0),
                               flow_state=c['birth_to_emission_flow_state'],
                               touch_bid_size=int(g[6]), touch_ask_size=int(g[7]),
                               touch_imbalance=ratio(g[6], g[7]), horizon_s=h, target_ns=target,
                               endpoint_group=int(p[2]), endpoint_cursor=int(p[1]), endpoint_ns=int(p[0]),
                               endpoint_age_ns=target - int(p[0]),
                               recognition_mid=(int(g[4]) + int(g[5])) / (2 * NS),
                               change_pct=100 * (int(p[4]) + int(p[5]) - int(g[4]) - int(g[5])) / (int(g[4]) + int(g[5])) if valid else None,
                               disposition='available' if valid else 'censored_or_boundary',
                               change=(int(p[4]) + int(p[5]) - int(g[4]) - int(g[5])) / (2 * NS) if valid else None))
    save('dipole-after-recognition.csv.gz', result)
    frame = pd.DataFrame(result)
    summaries = []
    for (h, state), group in frame.groupby(['horizon_s', 'flow_state']):
        g = group[group.disposition.eq('available')]
        oriented = g.change * g.birth_polarity
        summaries.append(dict(horizon_s=h, flow_state=state, n=len(group), available=len(g),
                              same=int((oriented > 0).sum()), flat=int((oriented == 0).sum()), opposite=int((oriented < 0).sum()),
                              mean_birth_oriented_change=oriented.mean()))
    save('dipole-after-recognition-summary.csv', summaries)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--embargo-seconds', type=int, default=600)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output
    OUT.mkdir(exist_ok=True)
    a = load_groups()
    frame, outcomes = opportunities(a)
    metrics = fit_arms(frame, outcomes, args.embargo_seconds)
    save('opportunities.csv.gz', frame)
    save('outcomes.csv.gz', outcomes)
    cohort_tables(frame, outcomes)
    dipole_followup(a)
    expected = {r['instance'] for r in rows(REVIEW + 'candidate-flow-transition-instances.csv')}
    assert set(frame.loc[frame.cohort.eq('original'), 'instance']) == expected
    dump('method.json', dict(version='NG-FLOW-BOOK-v1', source_revision=REV, groups_source=GROUPS,
                             opportunity_source=REVIEW + 'chronological-instance-index.csv',
                             n_groups=len(a), n_opportunities=len(frame), cohort_counts=frame.cohort.value_counts().to_dict(),
                             n_common_inputs=int(frame.four_arm_eligible.sum()), arms=ARMS,
                             baseline_note='Includes unsigned classified activity and prior price response; flow arm adds signed ratios.',
                             book_note='Displayed changes at unchanged touch prices; zero encoded on price moves with explicit same-price flags. No fill/cancel attribution.',
                             fit='Ridge alpha 10; train-only scale/intercept; expanding 40/60/80% splits; horizon purge plus stated embargo; same eligible rows and targets in all arms; no hyperparameter search.',
                             embargo_seconds=args.embargo_seconds,
                             endpoint='Last eligible group at or before anchor+h; integer clocks; target beyond session or crossing a reset/halt censored; staleness retained.',
                             limitations=['Family-selected opportunities, not all market opportunities.', 'All four dates are discovery; this comparison contains October 18 only.',
                                          'Ratios with zero classified volume are missing; common-input cohort excludes them.',
                                          'Adjacent cases/outcome windows dependent; no independent significance claim.',
                                          'Negative absolute predictions retained; ridge is an explanatory probe, not an admitted scoring model.',
                                          'Matching uses replacement, activity distance has no caliper; inspect balance.',
                                          'No simulator entries, costs or fills.']))
    print(frame.cohort.value_counts().to_string())
    print(metrics.groupby(['target', 'horizon_s', 'arm']).mae.mean().to_string())


if __name__ == '__main__':
    main()
