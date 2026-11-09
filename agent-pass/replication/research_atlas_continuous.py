"""Causal completed-second observations, then separate retrospective birth joins.

Reads retained evidence only. Does not run a detector, repair data or place orders.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import types

import numpy as np
import pandas as pd

from flow_book_discovery import GROUPS, REV, NS, rows
from research_atlas import group_matrix

HERE = Path(__file__).resolve().parent
ATLAS = HERE / 'research-atlas-v2'
OUT = ATLAS / 'continuous-prebirth-v1'
EVIDENCE_REV = '8f4c15083392233c28ad5c450d44fdc34a466a67'


def ratio(b, s):
    return (b - s).div((b + s).where(b + s > 0))


def flow_features(day):
    f = day[['second', 'buy', 'sell', 'unknown']].copy().reset_index(drop=True)
    f['decision_ns'] = (f.second + 1) * NS
    # A comparison of two roll-20 states needs 21 consecutive observed bins.
    contiguous = f.second.diff().eq(1)
    f['flow_available'] = contiguous.rolling(20).sum().eq(20)
    b, s = f.buy.rolling(20).sum(), f.sell.rolling(20).sum()
    f['roll_buy'], f['roll_sell'] = b, s
    f['ratio'] = ratio(b, s)
    f['before_ratio'] = f.ratio.shift()
    f['expired_buy'], f['expired_sell'] = f.buy.shift(20), f.sell.shift(20)
    f['early_buy'], f['early_sell'] = f.buy.shift(10).rolling(10).sum(), f.sell.shift(10).rolling(10).sum()
    f['late_buy'], f['late_sell'] = f.buy.rolling(10).sum(), f.sell.rolling(10).sum()
    f['early_ratio'] = ratio(f.early_buy, f.early_sell)
    f['late_ratio'] = ratio(f.late_buy, f.late_sell)
    f['fresh_buy5'], f['fresh_sell5'] = f.buy.rolling(5).sum(), f.sell.rolling(5).sum()
    f['fresh_ratio5'] = ratio(f.fresh_buy5, f.fresh_sell5)
    f['unknown5'] = f.unknown.rolling(5).sum()
    derived = [c for c in f if c not in ('second', 'buy', 'sell', 'unknown', 'decision_ns', 'flow_available')]
    f.loc[~f.flow_available, derived] = np.nan
    return f


def book_context(f, a):
    f = f.copy()
    t = f.decision_ns.to_numpy(dtype=np.int64)
    j = np.searchsorted(a[:, 0], t, side='left') - 1
    k = np.searchsorted(a[:, 0], t - 21 * NS, side='left') - 1
    jc, kc = np.maximum(j, 0), np.maximum(k, 0)
    ready = (j >= 0) & (k >= 0) & (a[jc, 7] == 1) & (a[kc, 7] == 1) & (a[jc, 8] == a[kc, 8])
    f['source_group'], f['source_cursor'] = j, a[jc, 1]
    f['quote_known_by_ns'], f['segment'] = a[jc, 0], a[jc, 8]
    f['quote_age_s'] = (t - a[jc, 0]) / NS
    f['book_available'] = ready
    f['input_available'] = f.flow_available & ready
    f['mid_raw2'] = a[jc, 2]
    f['spread_ticks'] = (a[jc, 4] - a[jc, 3]) / 1e6
    f['touch_imb'] = ratio(pd.Series(a[jc, 5]), pd.Series(a[jc, 6]))
    # The start is t-20s; t-21 above is only the previous-flow boundary check.
    p = np.maximum(np.searchsorted(a[:, 0], t - 20 * NS, side='left') - 1, 0)
    f['prior_ticks20'] = (a[jc, 2] - a[p, 2]) / 2e6
    f.loc[~ready, ['touch_imb', 'prior_ticks20', 'spread_ticks', 'mid_raw2']] = np.nan
    return f


def predicates(f):
    valid = f.get('input_available', f.flow_available)
    step = valid & f.ratio.abs().lt(f.before_ratio.abs())
    half = valid & f.late_ratio.abs().lt(f.early_ratio.abs())
    book = f.get('touch_imb', pd.Series(np.nan, index=f.index))
    price = f.get('prior_ticks20', pd.Series(np.nan, index=f.index))
    return {
        'step_weakening': step,
        'expiry_only_weakening': step & (f.buy + f.sell).eq(0) & (f.expired_buy + f.expired_sell).gt(0),
        'fresh_opposed_weakening': step & ((f.buy - f.sell) * f.before_ratio).lt(0),
        'flow_vanished': valid & f.before_ratio.notna() & f.ratio.isna(),
        'flow_resumed': valid & f.before_ratio.isna() & f.ratio.notna(),
        'half_weakening': half,
        'half_weakening_book_aligned': half & (book * f.ratio).gt(0),
        'half_weakening_book_opposed': half & (book * f.ratio).lt(0),
        'half_weakening_price_opposed': half & (price * f.ratio).lt(0),
        'half_weakening_fresh_book_opposed': half & (f.fresh_ratio5 * f.ratio).lt(0) & (book * f.ratio).lt(0),
    }


def event_rows(f):
    result = []
    for name, mask in predicates(f).items():
        v = f.loc[mask].copy()
        v['hypothesis'] = name
        # First observed true bin, and again only after false/unavailable or a gap.
        onset = mask & (~mask.shift(fill_value=False) | f.second.diff().ne(1))
        v['onset'] = onset.loc[mask]
        previous_available = f.input_available.shift(fill_value=False)
        v['left_censored_onset'] = (onset & (~previous_available | f.second.diff().ne(1))).loc[mask]
        result.append(v)
    return pd.concat(result, ignore_index=True)


def associate_births(events, births, names):
    result = []
    for name in names:
        times = np.sort(events.loc[events.hypothesis.eq(name), 'decision_ns'].to_numpy(dtype=np.int64))
        for c in births.itertuples():
            birth = int(c.birth_second) * NS
            lo, hi = np.searchsorted(times, [birth - 60 * NS, birth], side='left')
            result.append(dict(candidate_id=c.candidate_id, hypothesis=name,
                               birth_ns=birth, signals_in_prior60=int(hi - lo),
                               first_lead_s=(birth - int(times[lo])) / NS if hi > lo else np.nan,
                               last_lead_s=(birth - int(times[hi - 1])) / NS if hi > lo else np.nan))
    return pd.DataFrame(result)


def outcomes(events, f, a):
    parts = []
    for h in (5, 20, 60):
        v = events.copy()
        t = v.decision_ns.to_numpy(dtype=np.int64) + h * NS
        j = np.searchsorted(a[:, 0], t, side='right') - 1
        valid = (t <= a[-1, 0]) & (a[j, 7] == 1) & (a[j, 8] == v.segment.to_numpy())
        v['horizon_s'], v['target_ns'] = h, t
        v['target_group'], v['target_cursor'] = j, a[j, 1]
        v['target_quote_known_by_ns'] = a[j, 0]
        v['target_quote_age_s'] = (t - a[j, 0]) / NS
        v['outcome_available'] = valid
        v['change_ticks'] = np.where(valid, (a[j, 2] - v.mid_raw2) / 2e6, np.nan)
        v['flow_aligned_ticks'] = v.change_ticks * np.sign(v.ratio)
        future = f.set_index('decision_ns').ratio.reindex(t).to_numpy()
        v['future_ratio'] = np.where(valid, future, np.nan)
        v['flow_strength_change'] = abs(v.future_ratio) - abs(v.ratio)
        parts.append(v[['hypothesis', 'decision_ns', 'horizon_s', 'target_ns', 'target_group',
                        'target_cursor', 'target_quote_known_by_ns', 'target_quote_age_s',
                        'outcome_available', 'change_ticks', 'flow_aligned_ticks', 'future_ratio', 'flow_strength_change']])
    return pd.concat(parts, ignore_index=True)


def save(name, data):
    opts = {'compression': {'method': 'gzip', 'mtime': 0}} if name.endswith('.gz') else {}
    data.to_csv(OUT / name, index=False, **opts)


def main(operator_bytes=None):
    OUT.mkdir(exist_ok=True)
    flow_path = ATLAS / 'dipole-completed-group-flow.csv.gz'
    day = pd.read_csv(flow_path)
    a = group_matrix(rows(GROUPS))
    f = book_context(flow_features(day), a)
    events = event_rows(f)
    onsets = events[events.onset].copy()
    operator_path = ATLAS / 'sources/info_dipole_pinned.py'
    # Checkout line-ending conversion must not change the source identity.
    raw = operator_bytes if operator_bytes is not None else subprocess.check_output(['git', 'show', f'{REV}:odcore/info_dipole.py'])
    expected_hash = json.loads((ATLAS / 'dipole-application-method.json').read_text())['operator_sha256']
    assert hashlib.sha256(raw).hexdigest() == expected_hash
    operator = types.ModuleType('pinned_dipole')
    exec(compile(raw, str(operator_path), 'exec'), operator.__dict__)
    # One evaluation per unique onset time, reused by overlapping hypotheses.
    operator_rows = []
    for t in sorted(onsets.decision_ns.unique()):
        j = int(np.searchsorted(f.decision_ns, t))
        op = operator.signed_flow_features(f.buy.iloc[j-19:j+1], f.sell.iloc[j-19:j+1])
        operator_rows.append(dict(decision_ns=int(t), operator_defined=op is not None, **(op or {})))
    operators = pd.DataFrame(operator_rows)
    onsets = onsets.merge(operators, on='decision_ns', validate='many_to_one')
    births = pd.DataFrame(rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz'))
    names = list(predicates(f))
    links = associate_births(onsets, births, names)
    scored = outcomes(onsets, f, a)
    birth_times = np.sort(births.birth_second.to_numpy(dtype=np.int64) * NS)
    ts = onsets.decision_ns.to_numpy(dtype=np.int64)
    # Labels kept in their own table, never added to causal feature/event rows.
    labels = onsets[['hypothesis', 'decision_ns']].copy()
    labels['births_in_next60'] = np.searchsorted(birth_times, ts + 60*NS, side='right') - np.searchsorted(birth_times, ts, side='right')
    labels['birth_at_same_ns'] = np.searchsorted(birth_times, ts, side='right') - np.searchsorted(birth_times, ts, side='left')
    summaries = []
    for name in names:
        active = events[events.hypothesis.eq(name)]
        v = onsets[onsets.hypothesis.eq(name)]
        link = links[links.hypothesis.eq(name)]
        lab = labels[labels.hypothesis.eq(name)]
        summaries.append(dict(hypothesis=name, active_seconds=len(active), onsets=len(v),
            input_available_seconds=int(f.input_available.sum()), retained_births=len(births),
            births_with_prior_onset=int(link.signals_in_prior60.gt(0).sum()),
            median_last_lead_s=link.last_lead_s.median(),
            onsets_with_next_birth=int(lab.births_in_next60.gt(0).sum()),
            onsets_without_next_birth=int(lab.births_in_next60.eq(0).sum()),
            median_quote_age_s=v.quote_age_s.median(),
            left_censored_onsets=int(v.left_censored_onset.sum()),
            paper_disposition='retain_for_more_days'))
    summary = pd.DataFrame(summaries)
    metrics = []
    for (name, h), g in scored.groupby(['hypothesis', 'horizon_s']):
        v = g[g.outcome_available]
        end, clusters = -1, 0
        for r in v.sort_values('decision_ns').itertuples():
            clusters += int(r.decision_ns > end)
            end = max(end, r.target_ns)
        metrics.append(dict(hypothesis=name, horizon_s=int(h), n=len(g), available=len(v),
            unavailable=len(g)-len(v), up=int(v.change_ticks.gt(0).sum()), down=int(v.change_ticks.lt(0).sum()),
            flat=int(v.change_ticks.eq(0).sum()), interval_clusters=clusters,
            follows=int(v.flow_aligned_ticks.gt(0).sum()), opposes=int(v.flow_aligned_ticks.lt(0).sum()),
            direction_undefined=int(v.flow_aligned_ticks.isna().sum()),
            direction_balanced_nonflat=int((v.flow_aligned_ticks.eq(0) & v.change_ticks.ne(0)).sum()),
            median_abs_ticks=v.change_ticks.abs().median(), flow_comparable=int(v.flow_strength_change.notna().sum()),
            flow_weaker=int(v.flow_strength_change.lt(0).sum()), flow_stronger=int(v.flow_strength_change.gt(0).sum()),
            flow_same=int(v.flow_strength_change.eq(0).sum()), future_flow_undefined=int(v.future_ratio.isna().sum())))
    for name, table in [('observations.csv.gz', f), ('active-events.csv.gz', events),
                        ('onsets.csv.gz', onsets), ('birth-links.csv.gz', links),
                        ('onset-birth-labels.csv.gz', labels), ('outcomes.csv.gz', scored),
                        ('summary.csv', summary), ('outcome-summary.csv', pd.DataFrame(metrics))]:
        save(name, table)
    manifest = dict(evidence_revision=EVIDENCE_REV, source_revision=REV, source_groups=GROUPS,
        flow_sha256=hashlib.sha256(flow_path.read_bytes()).hexdigest(),
        operator_sha256=hashlib.sha256(raw).hexdigest(), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        session_date='2023-10-18', observation_seconds=len(f), input_available_seconds=int(f.input_available.sum()),
        hypotheses=names, retained_births=len(births), unique_onset_seconds=int(onsets.decision_ns.nunique()),
        clock='Decision is completed-second boundary; quote strictly earlier; 21-second same-segment history required. This is accounting availability, not measured processing or execution time.',
        onset='First true observed bin after false/unavailable/gap, separately per predicate. All active seconds retained; a state already true at first eligibility is left-censored, not a proven physical onset.',
        birth_alignment='Post-hoc [birth-60s, birth) report window only. All 863 births retained per predicate. No birth labels enter predicates; unlinked onsets retained.',
        limits=['One discovery session; no signal exclusion.', 'One-second observation floor is not earliest native-group information or recovered NG look-ahead.',
                'No original Family A identity supplied; frozen classifier/runway not assigned.',
                'No matched background, causal lift, profitability or execution claim; no-birth events are not false trades.',
                'Shared input groups, nested predicates and overlapping outcomes remain dependent.',
                'October 2/3/17 final repaired inputs not verified; CCODE owns repair.'])
    (OUT / 'method.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()
