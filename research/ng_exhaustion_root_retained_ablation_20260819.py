#!/usr/bin/env python3
from __future__ import annotations

import argparse, copy, json
from collections import Counter
from pathlib import Path

from ng_exhaustion_chain_recovery_features_20260819 import *
from ng_exhaustion_chain_recovery_models_20260819 import evaluate

TARGETS=('CONTINUATION','EVENTUAL_DEPTH','CHAIN_TYPE_FAMILY')


def zero_root(c):
    z=copy.deepcopy(c)
    root=copy.deepcopy(z['preds'][0])
    conf=event_confirm(root)
    dummy={
        'event_id':root.get('event_id','ROOT_ABLATED'),
        'week_sunday':root['week_sunday'],
        'sequence_index':root['sequence_index'],
        't0_idx':10**12,
        'polarity':0,
        'family':None,
        'pre_family_distances':[],
        'a_frozen_post_state':None,
        'seed_state':None,
        'feature':{},
        'dynamic_endpoint':{'causal_confirmation_idx':conf},
        'time_context':{},
    }
    z['preds'][0]=dummy
    return z


def block_delta(full, ablated):
    out={}
    for b in ('validation','confirmation','held'):
        f=full.get('blocks',{}).get(b,{})
        a=ablated.get('blocks',{}).get(b,{})
        if not f.get('n') or not a.get('n') or f.get('ids')!=a.get('ids'):
            out[b]={'n':0}; continue
        out[b]={
            'n':int(f['n']),
            'root_retained_minus_ablated_log_loss_improvement':float(a['log_loss']-f['log_loss']),
            'root_retained_minus_ablated_brier_improvement':float(a['brier']-f['brier']),
        }
    return out


def validated_increment(delta):
    for b in ('validation','confirmation'):
        q=delta.get(b,{})
        if q.get('n',0)<=0: return False
        if q.get('root_retained_minus_ablated_log_loss_improvement',0)<=0: return False
        if q.get('root_retained_minus_ablated_brier_improvement',0)<=0: return False
    h=delta.get('held',{})
    if h.get('n',0)>=20:
        if h.get('root_retained_minus_ablated_log_loss_improvement',0)<0: return False
        if h.get('root_retained_minus_ablated_brier_improvement',0)<0: return False
    return True


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True); ap.add_argument('--held',required=True)
    ap.add_argument('--base-lineage',required=True); ap.add_argument('--held-lineage',required=True)
    ap.add_argument('--raw-dir',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    events=load_events_full(a.base,a.held); lineage=load_lineage(a.base_lineage,a.held_lineage)
    exact=Counter(int(r['depth']) for r in lineage); assert dict(sorted(exact.items()))==EXPECTED_EXACT
    rows=[]
    for stage in (2,3):
        cases,censored=build_cases(events,lineage,stage); ablated=[zero_root(c) for c in cases]
        cache=load_price_cache(cases,a.raw_dir)
        for model in MODELS:
            for target in TARGETS:
                for phase,grid in (('PRIOR',PRIOR_AGES),('POST_BIRTH',POST_H)):
                    for sec in grid:
                        full=evaluate(model,cases,stage,phase,sec,cache,'FULL_CAUSAL',target)
                        abl=evaluate(model,ablated,stage,phase,sec,cache,'FULL_CAUSAL',target)
                        delta=block_delta(full,abl)
                        rows.append({
                            'stage':stage,'model':model,'target':target,'phase':phase,'seconds':int(sec),
                            'full':full,'root_ablated':abl,'root_increment':delta,
                            'root_increment_independently_validated':validated_increment(delta),
                        })
    out={
        'status':'NG_ROOT_RETAINED_VS_ABLATED_D2_D3_COMPLETE','date':DATE,
        'primary_question':'DOES_CAUSALLY_AVAILABLE_ROOT_INFORMATION_ADD_INCREMENTAL_PREDICTIVE_VALUE_AT_D2_D3_ON_IDENTICAL_ROWS_AND_CHECKPOINTS',
        'stages':[2,3],'targets':list(TARGETS),'models':list(MODELS),
        'prior_age_values':list(PRIOR_AGES),'post_birth_H_values':list(POST_H),
        'root_ablation_method':'ZERO_ONLY_THE_ROOT_FEATURE_BLOCK_WHILE_PRESERVING_ITS_CAUSAL_CONFIRMATION_FOR_IDENTICAL_CHECKPOINT_AND_ROW_ELIGIBILITY',
        'cross_model_vote_used':False,'frozen_exact_depth_counts':dict(sorted(exact.items())),'rows':rows,
        'policy':'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL','promotion_performed':False,
        'protected_mutations':{'detector':False,'canonical_rows':False,'phase1':False,'phase2':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')

if __name__=='__main__': main()
