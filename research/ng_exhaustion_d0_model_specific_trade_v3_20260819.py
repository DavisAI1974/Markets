#!/usr/bin/env python3
from __future__ import annotations

import json, sys
import ng_exhaustion_d0_model_specific_trade_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate, tune_param, predict_probs, align_probs

for name, value in {
    'MODELS':MODELS,'PRIOR_AGES':PRIOR_AGES,'EXPECTED_EXACT':EXPECTED_EXACT,'TICK':TICK,
    'load_events_full':load_events_full,'load_lineage':load_lineage,'build_cases':build_cases,
    'load_price_cache':load_price_cache,'dataset':dataset,'split_cases':split_cases,
    'event_confirm':event_confirm,'evaluate':evaluate,'tune_param':tune_param,
    'predict_probs':predict_probs,'align_probs':align_probs,
}.items(): setattr(base,name,value)


def main():
    base.main()
    p=sys.argv[sys.argv.index('--out')+1]
    d=json.load(open(p))
    d['status']='NG_D0_MODEL_SPECIFIC_TRADE_V3_COMPLETE'
    d['implementation_revision']=IMPLEMENTATION_REVISION
    d['live_market_policy']=LIVE_MARKET_POLICY
    d['target_polarity_is_primary_question']=False
    d['signal_surface']='V3_CONTINUOUS_LIVE_MARKET_STATE'
    open(p,'w').write(json.dumps(d,indent=2,sort_keys=True)+'\n')


if __name__=='__main__': main()
