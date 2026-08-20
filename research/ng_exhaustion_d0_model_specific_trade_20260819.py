#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

from ng_exhaustion_chain_recovery_features_20260819 import *
from ng_exhaustion_chain_recovery_models_20260819 import evaluate, tune_param, predict_probs, align_probs

THRESHOLDS = (0.75, 0.85, 0.90, 0.95, 0.975)
HOLDS = (5, 10, 20, 30, 60, 120, 300)
ORIENTATIONS = ('WITH_ROOT_POLARITY', 'AGAINST_ROOT_POLARITY')


def invert_cases(cases):
    out = []
    for c in cases:
        z = dict(c)
        z['continuation'] = 1 - int(c['continuation'])
        out.append(z)
    return out


def prows(model, param, trainset, testset, age, cache):
    Xtr, ytr, _, _, _ = dataset(trainset, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
    Xte, yte, weeks, leads, ids = dataset(testset, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
    if not len(yte):
        return []
    raw, cls = predict_probs(model, param, Xtr, ytr, Xte)
    if raw is None:
        return []
    p = align_probs(raw, cls, ['0', '1'])[:, 1]
    cmap = {c['id']: c for c in testset}
    return [
        {'id': cid, 'week': w, 'actual_d0': int(y), 'p_d0': float(pp), 'lead': int(lead), 'case': cmap[cid]}
        for cid, y, w, lead, pp in zip(ids, yte, weeks, leads, p)
    ]


def first_at_or_after(times, t):
    j = int(np.searchsorted(times, float(t), side='left'))
    return None if j >= len(times) else j


def fill_trade(cache, row, age, hold, orientation):
    c = row['case']
    root = c['preds'][0]
    conf = event_confirm(root)
    if conf is None:
        return None
    signal = int(conf) + int(age)
    next_t0 = int(c['target']['t0_idx'])
    if signal >= next_t0:
        return None
    boundary = min(signal + int(hold), next_t0)
    times = cache['times'][c['week']]
    prices = cache['prices'][c['week']]
    ie = first_at_or_after(times, signal)
    ix = first_at_or_after(times, boundary)
    if ie is None or ix is None or ix < ie:
        return None
    entry = float(prices[ie])
    exitp = float(prices[ix])
    seg = prices[ie:ix + 1]
    sign = float(root['polarity']) * (1.0 if orientation == 'WITH_ROOT_POLARITY' else -1.0)
    path = sign * (seg - entry) / TICK
    gross = sign * (exitp - entry) / TICK
    rng = float(np.max(path) - np.min(path)) if len(path) else 0.0
    return {
        'id': row['id'],
        'week': row['week'],
        'actual_d0': row['actual_d0'],
        'p_d0': row['p_d0'],
        'lead_seconds_to_next_event': row['lead'],
        'signal_time': signal,
        'entry_time': float(times[ie]),
        'exit_time': float(times[ix]),
        'planned_hold_seconds': int(hold),
        'next_event_capped': bool(signal + hold >= next_t0),
        'orientation': orientation,
        'gross_ticks': float(gross),
        'net_0_5_ticks': float(gross - 0.5),
        'net_1_ticks': float(gross - 1.0),
        'net_2_ticks': float(gross - 2.0),
        'mfe_ticks': float(np.max(path)) if len(path) else 0.0,
        'mae_ticks': float(np.min(path)) if len(path) else 0.0,
        'path_range_ticks': rng,
        'path_efficiency': abs(float(gross)) / max(rng, 1e-9),
    }


def summary(rows):
    if not rows:
        return {'n': 0}
    by = defaultdict(list)
    for r in rows:
        by[r['week']].append(r['net_1_ticks'])
    wmeans = [float(np.mean(v)) for v in by.values()]
    def m(k):
        return float(np.mean([r[k] for r in rows]))
    return {
        'n': len(rows),
        'actual_d0_fraction': m('actual_d0'),
        'mean_probability': m('p_d0'),
        'mean_lead_seconds_to_next_event': m('lead_seconds_to_next_event'),
        'mean_gross_ticks': m('gross_ticks'),
        'mean_net_0_5_ticks': m('net_0_5_ticks'),
        'mean_net_1_ticks': m('net_1_ticks'),
        'mean_net_2_ticks': m('net_2_ticks'),
        'mean_mfe_ticks': m('mfe_ticks'),
        'mean_mae_ticks': m('mae_ticks'),
        'mean_path_efficiency': m('path_efficiency'),
        'positive_week_fraction_net_1': float(np.mean([x > 0 for x in wmeans])) if wmeans else None,
        'weeks': len(by),
    }


def candidate(pred, cache, age, threshold, hold, orientation):
    return [
        z for r in pred if r['p_d0'] >= threshold
        for z in [fill_trade(cache, r, age, hold, orientation)] if z is not None
    ]


def reproduce_earliest_signal(model, d0, cache):
    tested = []
    for age in PRIOR_AGES:
        point = evaluate(model, d0, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
        tested.append({
            'root_age_seconds_after_confirmation': int(age),
            'independently_validated': bool(point['independently_validated']),
            'param': point.get('param'),
            'blocks': point.get('blocks', {}),
        })
        if point['independently_validated']:
            return int(age), point.get('param'), tested
    return None, None, tested


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, choices=MODELS)
    ap.add_argument('--base', required=True)
    ap.add_argument('--held', required=True)
    ap.add_argument('--base-lineage', required=True)
    ap.add_argument('--held-lineage', required=True)
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    events = load_events_full(a.base, a.held)
    lineage = load_lineage(a.base_lineage, a.held_lineage)
    exact = Counter(int(r['depth']) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT
    d1, censored = build_cases(events, lineage, 1)
    d0 = invert_cases(d1)
    assert sum(int(c['continuation'] == 1) for c in d0) == 135823
    assert sum(int(c['continuation'] == 0) for c in d0) == 20562
    assert len(censored) == 37
    cache = load_price_cache(d1, a.raw_dir)

    age, reproduced_param, signal_audit = reproduce_earliest_signal(a.model, d0, cache)
    if age is None:
        result = {
            'status': 'D0_MODEL_SPECIFIC_TRADE_BLOCKED_NO_INDEPENDENTLY_VALIDATED_SIGNAL',
            'model': a.model,
            'signal_reproduction': signal_audit,
            'probability_aggregation': 'NONE_MODEL_SPECIFIC_ONLY',
            'historically_validated_candidate': False,
        }
    else:
        fit = split_cases(d0, ('discovery_fit',))
        tune = split_cases(d0, ('discovery_tune',))
        train = fit + tune
        param = tune_param(a.model, fit, tune, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
        if param is None or param != reproduced_param:
            raise RuntimeError(f"D0 signal parameter reproduction mismatch model={a.model} age={age} eval={reproduced_param} trade={param}")
        tune_pred = prows(a.model, param, fit, tune, age, cache)
        scored = []
        for threshold in THRESHOLDS:
            for hold in HOLDS:
                for orientation in ORIENTATIONS:
                    s = summary(candidate(tune_pred, cache, age, threshold, hold, orientation))
                    scored.append({
                        'threshold': threshold,
                        'hold_seconds': hold,
                        'orientation': orientation,
                        'discovery_tune': s,
                    })
        eligible = [
            x for x in scored
            if x['discovery_tune'].get('n', 0) >= 200
            and x['discovery_tune'].get('mean_net_1_ticks') is not None
        ]
        eligible.sort(
            key=lambda x: (
                x['discovery_tune']['mean_net_1_ticks'],
                x['discovery_tune'].get('positive_week_fraction_net_1') or -1,
                x['discovery_tune']['n'],
            ),
            reverse=True,
        )
        sel = dict(eligible[0]) if eligible else None
        oot = {}
        valid = False
        if sel:
            for block in ('validation', 'confirmation', 'held'):
                pred = prows(a.model, param, train, split_cases(d0, (block,)), age, cache)
                oot[block] = summary(candidate(pred, cache, age, sel['threshold'], sel['hold_seconds'], sel['orientation']))
            va = oot.get('validation', {})
            co = oot.get('confirmation', {})
            he = oot.get('held', {})
            valid = (
                va.get('n', 0) >= 200
                and co.get('n', 0) >= 100
                and va.get('mean_net_1_ticks', -math.inf) > 0
                and co.get('mean_net_1_ticks', -math.inf) > 0
                and va.get('positive_week_fraction_net_1', 0) >= 0.5
                and co.get('positive_week_fraction_net_1', 0) >= 0.5
            )
            if he.get('n', 0) >= 50 and he.get('mean_net_1_ticks', -math.inf) < 0:
                valid = False
        result = {
            'status': 'D0_MODEL_SPECIFIC_TRADE_AGENT_COMPLETE',
            'model': a.model,
            'root_age_seconds_after_confirmation': age,
            'model_param': param,
            'signal_reproduction': signal_audit,
            'candidate_grid': {
                'thresholds': list(THRESHOLDS),
                'hold_seconds': list(HOLDS),
                'orientations': list(ORIENTATIONS),
            },
            'discovery_selected_candidate': sel,
            'top_discovery_candidates': eligible[:10],
            'frozen_candidate_OOT_blocks': oot,
            'historically_validated_candidate': bool(valid),
            'probability_aggregation': 'NONE_MODEL_SPECIFIC_ONLY',
        }

    out = {
        'status': 'NG_D0_MODEL_SPECIFIC_TRADE_COMPLETE',
        'date': DATE,
        'model': a.model,
        'signal_source': 'INDEPENDENTLY_REPRODUCED_FULL_CAUSAL_D0_TERMINALITY_MODEL',
        'trade_window_capped_at_next_canonical_exhaustion': True,
        'entry_fill': 'FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_SIGNAL',
        'exit_fill': 'FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_HORIZON_OR_NEXT_EVENT_CAP',
        'result': result,
        'frozen_exact_depth_counts': dict(sorted(exact.items())),
        'exact_d0_preserved_n': 135860,
        'executable_exact_d0_n': 135823,
        'd1plus_controls_n': 20562,
        'censored_d0': len(censored),
        'cross_model_vote_used': False,
        'policy': 'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL',
        'promotion_performed': False,
        'protected_mutations': {
            'detector': False,
            'canonical_rows': False,
            'phase1': False,
            'phase2': False,
            'runway_clock': False,
            'permanent_frankie': False,
            'frankie_1': False,
            'spawn_py': False,
            'ssos_play': False,
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'status': out['status'],
        'model': a.model,
        'trade_status': result['status'],
        'root_age': result.get('root_age_seconds_after_confirmation'),
        'historically_validated_candidate': result.get('historically_validated_candidate', False),
    }, indent=2))


if __name__ == '__main__':
    main()
