#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from collections import Counter
from pathlib import Path
import numpy as np

from ng_exhaustion_chain_recovery_features_20260819 import *
from ng_exhaustion_chain_recovery_models_20260819 import tune_param, predict_probs, align_probs


def invert_cases(cases):
    out = []
    for c in cases:
        z = dict(c)
        z['continuation'] = 1 - int(c['continuation'])
        out.append(z)
    return out


def probability_rows(model, param, trainset, testset, age, cache):
    Xtr, ytr, _, _, _ = dataset(trainset, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
    Xte, yte, weeks, leads, ids = dataset(testset, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
    if not len(yte):
        return None
    raw, cls = predict_probs(model, param, Xtr, ytr, Xte)
    if raw is None:
        return None
    p = align_probs(raw, cls, ['0', '1'])[:, 1]
    return {'ids': ids, 'y': np.asarray(yte, dtype=object), 'p': p, 'weeks': weeks, 'leads': leads}


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
    assert sum(c['continuation'] for c in d0) == 135823
    assert len(censored) == 37
    cache = load_price_cache(d1, a.raw_dir)

    fit1 = split_cases(d1, ('discovery_fit',))
    tune1 = split_cases(d1, ('discovery_tune',))
    train1 = fit1 + tune1
    fit0 = split_cases(d0, ('discovery_fit',))
    tune0 = split_cases(d0, ('discovery_tune',))
    train0 = fit0 + tune0
    findings = []
    for age in PRIOR_AGES:
        p1 = tune_param(a.model, fit1, tune1, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
        p0 = tune_param(a.model, fit0, tune0, 1, 'PRIOR', age, cache, 'FULL_CAUSAL', 'CONTINUATION')
        point = {
            'model': a.model,
            'root_age_seconds_after_confirmation': int(age),
            'd1_param': p1,
            'd0_param': p0,
            'blocks': {},
        }
        if p1 is None or p0 is None:
            findings.append(point)
            continue
        for block in ('validation', 'confirmation', 'held'):
            r1 = probability_rows(a.model, p1, train1, split_cases(d1, (block,)), age, cache)
            r0 = probability_rows(a.model, p0, train0, split_cases(d0, (block,)), age, cache)
            if r1 is None or r0 is None:
                point['blocks'][block] = {'n': 0}
                continue
            assert r1['ids'] == r0['ids']
            y1 = np.asarray([int(x) for x in r1['y']])
            y0 = np.asarray([int(x) for x in r0['y']])
            assert np.array_equal(y0, 1 - y1)
            err = np.asarray(r0['p']) + np.asarray(r1['p']) - 1.0
            point['blocks'][block] = {
                'n': int(len(err)),
                'mean_abs_probability_complement_error': float(np.mean(np.abs(err))),
                'max_abs_probability_complement_error': float(np.max(np.abs(err))),
                'mean_signed_probability_complement_error': float(np.mean(err)),
                'matched_ids': True,
                'labels_are_exact_complements': True,
            }
        findings.append(point)

    out = {
        'status': 'NG_D0_D1_COMPLEMENT_MODEL_AGENT_COMPLETE',
        'date': DATE,
        'model': a.model,
        'interpretation': 'D0_TERMINALITY_AND_D1_CONTINUATION_ARE_THE_SAME_BINARY_BOUNDARY_WITH_COMPLEMENTARY_LABELS_ON_IDENTICAL_EXECUTABLE_ROWS; THIS_IS_AN_IMPLEMENTATION_CALIBRATION_CHECK_NOT_NEW_INDEPENDENT_EVIDENCE',
        'primary_information_view': 'FULL_CAUSAL',
        'root_clock': 'ROOT_AGE_MATCHED_TO_D1_PRIOR_AGE',
        'root_age_values': list(PRIOR_AGES),
        'cross_model_vote_used': False,
        'frozen_exact_depth_counts': dict(sorted(exact.items())),
        'executable_rows': len(d1),
        'censored_d0': len(censored),
        'findings': findings,
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
        'max_complement_error': max(
            [b.get('max_abs_probability_complement_error', 0.0)
             for f in findings for b in f.get('blocks', {}).values()] or [0.0]
        ),
    }, indent=2))


if __name__ == '__main__':
    main()
