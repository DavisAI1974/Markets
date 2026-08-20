#!/usr/bin/env python3
from __future__ import annotations

import json, sys
import ng_exhaustion_root_retained_ablation_20260819 as base
from ng_exhaustion_chain_recovery_features_v3_20260819 import *
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate

for name, value in {
    'MODELS':MODELS,'PRIOR_AGES':PRIOR_AGES,'POST_H':POST_H,'EXPECTED_EXACT':EXPECTED_EXACT,
    'load_events_full':load_events_full,'load_lineage':load_lineage,'build_cases':build_cases,
    'load_price_cache':load_price_cache,'event_confirm':event_confirm,'evaluate':evaluate,
}.items(): setattr(base,name,value)


def main():
    base.main()
    p=sys.argv[sys.argv.index('--out')+1]
    d=json.load(open(p))
    d['status']='NG_ROOT_RETAINED_VS_ABLATED_V3_AGENT_COMPLETE'
    d['implementation_revision']=IMPLEMENTATION_REVISION
    d['live_market_policy']=LIVE_MARKET_POLICY
    d['target_polarity_is_primary_question']=False
    d['primary_chain_type_policy']=PRIMARY_CHAIN_TYPE_POLICY
    open(p,'w').write(json.dumps(d,indent=2,sort_keys=True)+'\n')


if __name__=='__main__': main()
