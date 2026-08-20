#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from collections import Counter
from pathlib import Path

import ng_exhaustion_root_retained_ablation_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate

TARGETS = base.TARGETS
zero_root = base.zero_root
block_delta = base.block_delta
validated_increment = base.validated_increment


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, type=int, choices=(2, 3))
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

    cases, censored = build_cases(events, lineage, a.stage)
    ablated = [zero_root(c) for c in cases]
    cache = load_price_cache(cases, a.raw_dir)
    rows = []
    checkpoints = [('PRIOR', s) for s in PRIOR_AGES] + [(BIRTH_T0_PHASE, 0)] + [('POST_BIRTH', s) for s in POST_H]
    for target in TARGETS:
        for phase, sec in checkpoints:
            full = evaluate(a.model, cases, a.stage, phase, sec, cache, 'FULL_CAUSAL', target)
            abl = evaluate(a.model, ablated, a.stage, phase, sec, cache, 'FULL_CAUSAL', target)
            delta = block_delta(full, abl)
            rows.append({
                'stage': a.stage,
                'model': a.model,
                'target': target,
                'phase': phase,
                'seconds': int(sec),
                'full': full,
                'root_ablated': abl,
                'root_increment': delta,
                'root_increment_independently_validated': validated_increment(delta),
            })

    out = {
        'status': 'NG_ROOT_RETAINED_VS_ABLATED_V3_AGENT_COMPLETE',
        'date': DATE,
        'stage': int(a.stage),
        'model': a.model,
        'implementation_revision': IMPLEMENTATION_REVISION,
        'live_market_policy': LIVE_MARKET_POLICY,
        'target_polarity_is_primary_question': False,
        'primary_chain_type_policy': PRIMARY_CHAIN_TYPE_POLICY,
        'primary_question': 'DOES_CAUSALLY_AVAILABLE_ROOT_INFORMATION_ADD_INCREMENTAL_PREDICTIVE_VALUE_AT_D2_D3_ON_IDENTICAL_ROWS_AND_CHECKPOINTS',
        'targets': list(TARGETS),
        'timing_ladder': list(TIMING_LADDER),
        'prior_age_values': list(PRIOR_AGES),
        'birth_T0_values': [0],
        'post_birth_H_values': list(POST_H),
        'case_n': int(len(cases)),
        'censored_n': int(len(censored)),
        'root_ablation_method': 'ZERO_ONLY_THE_ROOT_EVENT_BLOCK_WHILE_PRESERVING_IDENTICAL_CHECKPOINT_ROW_ELIGIBILITY_AND_THE_SAME_CONTINUOUS_LIVE_MARKET_VECTOR_ON_BOTH_SIDES',
        'cross_model_vote_used': False,
        'frozen_exact_depth_counts': dict(sorted(exact.items())),
        'rows': rows,
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
        'stage': a.stage,
        'model': a.model,
        'validated_root_increments': sum(int(r['root_increment_independently_validated']) for r in rows),
    }, indent=2))


if __name__=='__main__': main()
