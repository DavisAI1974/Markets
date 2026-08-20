#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import ng_exhaustion_d0_d3_model_specific_trade_v3_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import BIRTH_T0_PHASE, POST_H, PRIOR_AGES
from ng_exhaustion_v3_later_prior_refinement_20260819 import SEARCH_GRID, support_possible

IMPLEMENTATION_REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE_T0_FULL_PRIOR_HIERARCHY_FIXED_HORIZON_TRADE"


def _record(phase, sec, q):
    return {
        "phase": phase,
        "seconds": int(sec),
        "independently_validated": bool(q["independently_validated"]),
        "param": q.get("param"),
        "blocks": q.get("blocks", {}),
    }


def signal_scan(model: str, cases, engine_stage: int, trade_stage: int, cache):
    """Find the earliest signal under the true chronology hierarchy.

    Search every eligible PRIOR checkpoint first. Only after PRIOR is exhausted may
    D1-D3 use the birth second T0, then H+1..H+5. D0 has no descendant-birth fallback.
    """
    tested = []
    for age in PRIOR_AGES:
        q = base.evaluate(model, cases, engine_stage, "PRIOR", age, cache, "FULL_CAUSAL", base.TARGET)
        tested.append(_record("PRIOR", age, q))
        if q["independently_validated"]:
            return "PRIOR", int(age), q.get("param"), tested

    for age in SEARCH_GRID:
        possible, counts = support_possible(cases, engine_stage, age, base.TARGET)
        if not possible:
            tested.append({
                "phase": "PRIOR",
                "seconds": int(age),
                "support_possible": False,
                "support_counts": {b: dict(c) for b, c in counts.items()},
                "independently_validated": False,
                "param": None,
                "blocks": {},
            })
            break
        q = base.evaluate(model, cases, engine_stage, "PRIOR", age, cache, "FULL_CAUSAL", base.TARGET)
        z = _record("PRIOR", age, q)
        z["support_possible"] = True
        z["support_counts"] = {b: dict(c) for b, c in counts.items()}
        tested.append(z)
        if q["independently_validated"]:
            return "PRIOR", int(age), q.get("param"), tested

    if trade_stage == 0:
        return None, None, None, tested

    q = base.evaluate(model, cases, engine_stage, BIRTH_T0_PHASE, 0, cache, "FULL_CAUSAL", base.TARGET)
    tested.append(_record(BIRTH_T0_PHASE, 0, q))
    if q["independently_validated"]:
        return BIRTH_T0_PHASE, 0, q.get("param"), tested

    for h in POST_H:
        q = base.evaluate(model, cases, engine_stage, "POST_BIRTH", h, cache, "FULL_CAUSAL", base.TARGET)
        tested.append(_record("POST_BIRTH", h, q))
        if q["independently_validated"]:
            return "POST_BIRTH", int(h), q.get("param"), tested
    return None, None, None, tested


base.signal_scan = signal_scan
base.IMPLEMENTATION_REVISION = IMPLEMENTATION_REVISION


def main():
    base.main()
    p = sys.argv[sys.argv.index('--out') + 1]
    d = json.load(open(p))
    d['implementation_revision'] = IMPLEMENTATION_REVISION
    d['timing_hierarchy'] = 'ALL_ELIGIBLE_PRIOR_OUTRANKS_T0; T0_OUTRANKS_H; H_BEGINS_AT_PLUS_1_ONLY'
    d['T0_semantics'] = 'FROZEN_TARGET_BIRTH_SECOND_ITSELF_NOT_H_ZERO'
    r = d.get('result', {})
    if r.get('signal_phase') == BIRTH_T0_PHASE:
        r['signal_timing_interpretation'] = 'HISTORICAL_BIRTH_T0_SIGNAL; LIVE_EXECUTION_REQUIRES_PROVEN_UPSTREAM_EVENT_MARK_TIME_AT_OR_BEFORE_T0'
    elif r.get('signal_phase') == 'POST_BIRTH':
        r['signal_timing_interpretation'] = 'HISTORICAL_POST_BIRTH_SIGNAL; LIVE_EXECUTION_REQUIRES_PROVEN_UPSTREAM_EVENT_MARK_TIME'
    elif r.get('signal_phase') == 'PRIOR':
        r['signal_timing_interpretation'] = 'LIVE_EXECUTABLE_PRIOR_SIGNAL_SUBJECT_TO_ORDINARY_DATA_AVAILABILITY'
    d['result'] = r
    open(p, 'w').write(json.dumps(d, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
