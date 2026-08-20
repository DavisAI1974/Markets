#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import ng_exhaustion_d1_d5_chain_birth_agents_20260819 as frozen
from ng_exhaustion_chain_recovery_features_v3_20260819 import (
    DATE, EXPECTED_EXACT, VIEWS, build_cases, checkpoint, load_events_full,
    load_lineage, load_price_cache, split_cases, target_label,
)
from ng_exhaustion_chain_recovery_models_v3_20260819 import evaluate

DENSE_PRIOR = tuple(range(6, 61))
MID_PRIOR = tuple(range(65, 301, 5))
LATE_PRIOR = tuple(range(315, 901, 15))
TAIL_PRIOR = tuple(range(930, 3601, 30))
SEARCH_GRID = DENSE_PRIOR + MID_PRIOR + LATE_PRIOR + TAIL_PRIOR
MODELS = frozen.MODELS


def invert_d0(cases):
    out=[]
    for c in cases:
        z=dict(c); z['continuation']=1-int(c['continuation']); out.append(z)
    return out


def setup_target(events, lineage, stage: int, target: str):
    if stage == 0:
        original,censored=build_cases(events,lineage,1)
        if target=='D0_TERMINALITY': return invert_d0(original),censored,1,'CONTINUATION'
        if target=='EVENTUAL_DEPTH': return original,censored,1,'EVENTUAL_DEPTH'
        if target=='FIRST_CHAIN_TYPE': return original,censored,1,'CHAIN_TYPE_FAMILY'
        raise ValueError(target)
    cases,censored=build_cases(events,lineage,stage)
    if target not in ('CONTINUATION','EVENTUAL_DEPTH','CHAIN_TYPE_FAMILY'): raise ValueError(target)
    return cases,censored,stage,target


def eligible_label_counts(cases, phase, sec, target):
    out={}
    for block in ('validation','confirmation'):
        cnt=Counter()
        for c in cases:
            if c['block']!=block or checkpoint(c,phase,sec) is None: continue
            y=target_label(c,target)
            if y is not None: cnt[str(y)]+=1
        out[block]=cnt
    return out


def support_possible(cases, stage: int, sec: int, target: str):
    counts=eligible_label_counts(cases,'PRIOR',sec,target)
    if target=='CONTINUATION':
        req=frozen.MIN_COUNTS[stage]
        for block in ('validation','confirmation'):
            q=counts[block]
            if q.get('1',0)<req[f'{block}_pos'] or q.get('0',0)<req[f'{block}_neg']:
                return False,counts
        return True,counts
    floors={1:{'validation':200,'confirmation':100},2:{'validation':30,'confirmation':15},3:{'validation':10,'confirmation':5}}
    for block in ('validation','confirmation'):
        q=counts[block]
        if sum(q.values())<floors[stage][block] or len(q)<2:
            return False,counts
    return True,counts


def eval_age(model,cases,stage,age,cache,target):
    views={v:evaluate(model,cases,stage,'PRIOR',age,cache,v,target) for v in VIEWS}
    return {
        'prior_age_seconds':int(age),
        'views':views,
        'full_validated':bool(views['FULL_CAUSAL']['independently_validated']),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stage',type=int,required=True,choices=(0,1,2,3))
    ap.add_argument('--model',required=True,choices=MODELS)
    ap.add_argument('--target',required=True)
    ap.add_argument('--base',required=True); ap.add_argument('--held',required=True)
    ap.add_argument('--base-lineage',required=True); ap.add_argument('--held-lineage',required=True)
    ap.add_argument('--raw-dir',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args()

    events=load_events_full(a.base,a.held); lineage=load_lineage(a.base_lineage,a.held_lineage)
    exact=Counter(int(r['depth']) for r in lineage); assert dict(sorted(exact.items()))==EXPECTED_EXACT
    cases,censored,engine_stage,engine_target=setup_target(events,lineage,a.stage,a.target)
    cache=load_price_cache(cases,a.raw_dir)
    tested=[]; earliest=None; support_exhausted=False; support_exhaustion_age=None; previous_age=5

    for age in SEARCH_GRID:
        possible,counts=support_possible(cases,engine_stage,age,engine_target)
        if not possible:
            support_exhausted=True; support_exhaustion_age=int(age)
            tested.append({'prior_age_seconds':int(age),'support_possible':False,'support_counts':{b:dict(c) for b,c in counts.items()}})
            break
        point=eval_age(a.model,cases,engine_stage,age,cache,engine_target)
        point['support_possible']=True; point['support_counts']={b:dict(c) for b,c in counts.items()}
        tested.append(point)
        if point['full_validated']:
            # A coarse later checkpoint that passes is locally refined to every
            # intervening second after the previous tested grid point.
            if age-previous_age>1:
                refined=[]
                for s in range(previous_age+1,age):
                    possible2,counts2=support_possible(cases,engine_stage,s,engine_target)
                    if not possible2: break
                    z=eval_age(a.model,cases,engine_stage,s,cache,engine_target)
                    z['support_possible']=True; z['support_counts']={b:dict(c) for b,c in counts2.items()}
                    refined.append(z)
                    if z['full_validated']:
                        earliest={'timing_class':'PRIOR_BEFORE_BIRTH','prior_age_seconds':int(s),'view':'FULL_CAUSAL','refined_from_grid_checkpoint':int(age)}
                        break
                tested.extend(refined)
            if earliest is None:
                earliest={'timing_class':'PRIOR_BEFORE_BIRTH','prior_age_seconds':int(age),'view':'FULL_CAUSAL','refined_from_grid_checkpoint':None}
            break
        previous_age=age

    out={
        'status':'NG_EXHAUSTION_V3_LATER_PRIOR_REFINEMENT_AGENT_COMPLETE',
        'date':DATE,'stage':int(a.stage),'model':a.model,'target':a.target,
        'engine_stage':engine_stage,'engine_target':engine_target,
        'search_rule':'PRIOR_ONLY_BEFORE_ANY_POST_BIRTH_FALLBACK; EARLY_PRIOR_0_5_ASSUMED_ALREADY_TESTED',
        'search_grid':{'dense_6_60_every_1':list(DENSE_PRIOR),'mid_65_300_every_5':list(MID_PRIOR),'late_315_900_every_15':list(LATE_PRIOR),'tail_930_3600_every_30':list(TAIL_PRIOR),'local_refine_on_pass':True},
        'earliest_later_prior':earliest,
        'support_exhausted':support_exhausted,'support_exhaustion_age':support_exhaustion_age,
        'tested':tested,'censored_n':len(censored),
        'frozen_exact_depth_counts':dict(sorted(exact.items())),
        'cross_model_vote_used':False,'target_polarity_required':False,
        'promotion_performed':False,'policy':'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL',
        'protected_mutations':{'detector':False,'canonical_rows':False,'phase1':False,'phase2':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':out['status'],'stage':a.stage,'model':a.model,'target':a.target,'earliest_later_prior':earliest,'support_exhausted':support_exhausted,'support_exhaustion_age':support_exhaustion_age},indent=2))


if __name__=='__main__': main()
