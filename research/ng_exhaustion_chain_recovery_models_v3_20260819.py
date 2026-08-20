#!/usr/bin/env python3
from __future__ import annotations

from ng_exhaustion_chain_recovery_features_v3_20260819 import *
import ng_exhaustion_chain_recovery_models_v2_20260819 as base

# The V2 model code is unchanged statistically; V3 changes only the causal feature
# surface. Rebind the dataset lookup used by every tuning/OOT function so the exact
# same independent-model gates operate on the continuous live checkpoint state.
base.dataset = dataset
base.split_cases = split_cases

scale = base.scale
fit_model = base.fit_model
predict_probs = base.predict_probs
align_probs = base.align_probs
null_probs = base.null_probs
multiclass_brier = base.multiclass_brier
metrics = base.metrics
tune_param = base.tune_param
score_block = base.score_block
support_ok = base.support_ok
independent_pass = base.independent_pass
evaluate = base.evaluate
price_increment = base.price_increment
