#!/usr/bin/env python3
from __future__ import annotations

import ng_exhaustion_chain_birth_depth_type_recovery_v2_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate, price_increment

_orig_model_stage = base.model_stage
_orig_sparse_stage = base.sparse_stage

# Rebind the V2 orchestration to the V3 causal feature/model surface.
base.build_cases = build_cases
base.load_events_full = load_events_full
base.load_lineage = load_lineage
base.load_price_cache = load_price_cache
base.feature_row = feature_row
base.evaluate = evaluate
base.price_increment = price_increment
base.PRIOR_AGES = PRIOR_AGES
base.POST_H = POST_H
base.VIEWS = VIEWS


def model_stage(stage, model, events, lineage, raw_dir):
    r = _orig_model_stage(stage, model, events, lineage, raw_dir)
    r["status"] = "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_V3_COMPLETE"
    r["implementation_revision"] = IMPLEMENTATION_REVISION
    r["live_market_policy"] = LIVE_MARKET_POLICY
    r["prior_target_polarity_requirement"] = "NONE; UNKNOWN_TARGET_POLARITY_NEVER_BLOCKS_OR_FAILS_PRIOR"
    r["primary_chain_type_policy"] = PRIMARY_CHAIN_TYPE_POLICY
    return r


def sparse_stage(stage, events, lineage, raw_dir):
    r = _orig_sparse_stage(stage, events, lineage, raw_dir)
    r["status"] = "NG_CHAIN_BIRTH_DEPTH_TYPE_SPARSE_CASE_STUDY_V3_COMPLETE"
    r["implementation_revision"] = IMPLEMENTATION_REVISION
    r["live_market_policy"] = LIVE_MARKET_POLICY
    r["prior_target_polarity_requirement"] = "NONE"
    r["primary_chain_type_policy"] = PRIMARY_CHAIN_TYPE_POLICY
    return r


base.model_stage = model_stage
base.sparse_stage = sparse_stage


def main():
    base.main()


if __name__ == "__main__":
    main()
