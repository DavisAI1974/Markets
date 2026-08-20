#!/usr/bin/env python3
from __future__ import annotations

import ng_exhaustion_d0_full_causal_recovery_v2_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate, price_increment

_orig_run_model = base.run_model

base.build_cases = build_cases
base.load_events_full = load_events_full
base.load_lineage = load_lineage
base.load_price_cache = load_price_cache
base.evaluate = evaluate
base.price_increment = price_increment
base.PRIOR_AGES = PRIOR_AGES
base.VIEWS = VIEWS


def run_model(model, events, lineage, raw_dir):
    r = _orig_run_model(model, events, lineage, raw_dir)
    r["status"] = "NG_D0_FULL_CAUSAL_RECOVERY_V3_MODEL_AGENT_COMPLETE"
    r["implementation_revision"] = IMPLEMENTATION_REVISION
    r["live_market_policy"] = LIVE_MARKET_POLICY
    r["prior_target_polarity_requirement"] = "NONE; UNKNOWN_DESCENDANT_POLARITY_NEVER_BLOCKS_OR_FAILS_ROOT_PRIOR"
    r["primary_chain_type_policy"] = PRIMARY_CHAIN_TYPE_POLICY
    return r


base.run_model = run_model


def main():
    base.main()


if __name__ == "__main__":
    main()
