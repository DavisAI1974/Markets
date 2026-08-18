#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path

HORIZONS=(5,10,20,30,60,120,300)
DEPTHS=(2,3,4,5)
FALLBACK_CHECKPOINTS=(1,2,3,4,5,10,15,20,30,45,60,90,120,180,300,600,900,1800,3600)


def q(xs,p):
    a=sorted(float(x) for x in xs)
    if not a:return None
    z=(len(a)-1)*p;i=int(math.floor(z));j=int(math.ceil(z))
    return a[i] if i==j else a[i]*(j-z)+a[j]*(z-i)

def summ(xs):
    a=[float(x) for x in xs]
    return {'n':len(a),'min':min(a) if a else None,'p25':q(a,.25),'median':statistics.median(a) if a else None,'p75':q(a,.75),'p90':q(a,.90),'p95':q(a,.95),'max':max(a) if a else None}

def load_events(*paths):
    by=defaultdict(dict)
    for p in paths:
        with gzip.open(p,'rt') as f:
            for line in f:
                r=json.loads(line);by[r['week_sunday']][int(r['sequence_index'])]=r
    return by

def load_lineage(*paths):
    out=[]
    for p in paths:
        with gzip.open(p,'rt') as f:
            for line in f:out.append(json.loads(line))
    return out

def category(ready,target_t0,target_confirm):
    if ready<=target_t0:return 'READY_BY_TARGET_T0'
    if target_confirm is None:return 'TARGET_ENDPOINT_CENSORED'
    if ready<=target_confirm+5:return 'READY_BY_TARGET_ENDPOINT_PLUS5'
    if ready<=target_confirm+60:return 'READY_BY_TARGET_ENDPOINT_PLUS60'
    if ready<=target_confirm+120:return 'READY_BY_TARGET_ENDPOINT_PLUS120'
    if ready<=target_confirm+300:return 'READY_BY_TARGET_ENDPOINT_PLUS300'
    return 'LATER_THAN_TARGET_ENDPOINT_PLUS300'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True);ap.add_argument('--held',required=True)
    ap.add_argument('--base-lineage',required=True);ap.add_argument('--held-lineage',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    events=load_events(a.base,a.held);lineage=load_lineage(a.base_lineage,a.held_lineage)
    exact=Counter(int(r.get('all_model_consecutive_positive_depth',0)) for r in lineage)
    rows=[r for r in lineage if int(r.get('all_model_consecutive_positive_depth',0)) in DEPTHS]
    if len(rows)!=1725:raise SystemExit(f'expected 1725 D2+ rows, got {len(rows)}')
    table={}; hard=[]
    for h in HORIZONS:
        table[str(h)]={}
        for d in DEPTHS:
            cats=Counter();lag_t0=[];lag_ep5=[];perblock=defaultdict(Counter)
            n=0
            for lr in rows:
                if int(lr['all_model_consecutive_positive_depth'])!=d:continue
                n+=1;w=lr['week_sunday'];i=int(lr['origin_sequence_index']);rs=events[w]
                target=rs.get(i+d)
                if target is None:
                    cats['MISSING_TARGET_ROW']+=1;hard.append({'type':'missing_target','week':w,'origin_sequence_index':i,'depth':d});continue
                conf=[]
                for j in range(i,i+d):
                    e=rs.get(j);c=None if e is None else (e.get('dynamic_endpoint') or {}).get('causal_confirmation_idx')
                    if c is None:break
                    conf.append(int(c))
                if len(conf)!=d:
                    cats['ANCESTOR_ENDPOINT_CENSORED']+=1;continue
                ready=max(x+h for x in conf);t0=int(target['t0_idx']);tc=(target.get('dynamic_endpoint') or {}).get('causal_confirmation_idx');tc=None if tc is None else int(tc)
                cat=category(ready,t0,tc);cats[cat]+=1
                lag_t0.append(ready-t0)
                if tc is not None:lag_ep5.append(ready-(tc+5))
                perblock[str(lr.get('fold'))][cat]+=1
            table[str(h)][f'D{d}']={
                'n':n,'availability_categories':dict(cats),
                'ready_by_target_t0_or_endpoint_plus5':cats['READY_BY_TARGET_T0']+cats['READY_BY_TARGET_ENDPOINT_PLUS5'],
                'ready_by_target_endpoint_plus60_or_earlier':cats['READY_BY_TARGET_T0']+cats['READY_BY_TARGET_ENDPOINT_PLUS5']+cats['READY_BY_TARGET_ENDPOINT_PLUS60'],
                'required_info_ready_minus_target_t0_seconds':summ(lag_t0),
                'required_info_ready_minus_target_endpoint_plus5_seconds':summ(lag_ep5),
                'by_fold':{k:dict(v) for k,v in sorted(perblock.items())},
            }
    h5=table['5']
    result={
        'status':'HIGHER_ORDER_LATE_ENTRY_REVIVAL_AUDIT_COMPLETE',
        'date':'2026-08-18',
        'scope':'all exact D2-D5 frozen Phase-1 lineage instances; no row filtering',
        'exact_depth_counts':{f'D{d}':exact[d] for d in DEPTHS},
        'total_D2_plus':sum(exact[d] for d in DEPTHS),
        'preserve_all':True,'filtered_rows':0,
        'frozen_information_horizons_seconds':list(HORIZONS),
        'fallback_survivorship_checkpoints_seconds':list(FALLBACK_CHECKPOINTS),
        'entry_hierarchy':'KEEP_EARLIEST_VALIDATED_EARLY_ENTRY; FALLBACK_CHECKPOINTS_ONLY_FOR_NOT_INITIALLY_ACTIONABLE_CASES',
        'availability_by_horizon_and_depth':table,
        'headline_h5':{
            'D2_ready_by_t0_or_endpoint_plus5':h5['D2']['ready_by_target_t0_or_endpoint_plus5'],
            'D2_total':h5['D2']['n'],
            'D3_ready_by_t0_or_endpoint_plus5':h5['D3']['ready_by_target_t0_or_endpoint_plus5'],
            'D3_total':h5['D3']['n'],
            'D4_ready_by_t0_or_endpoint_plus5':h5['D4']['ready_by_target_t0_or_endpoint_plus5'],
            'D4_total':h5['D4']['n'],
            'D5_ready_by_t0_or_endpoint_plus5':h5['D5']['ready_by_target_t0_or_endpoint_plus5'],
            'D5_total':h5['D5']['n'],
            'remaining_ready_by_endpoint_plus60':sum(h5[f'D{d}']['availability_categories'].get('READY_BY_TARGET_ENDPOINT_PLUS60',0) for d in DEPTHS),
        },
        'interpretation':[
            'No D2+ structural instance is killed because an earlier information horizon was unavailable at the original target t0.',
            'Availability is not predictive skill. The audit only establishes when frozen predecessor information becomes causal relative to the target and reference entry clocks.',
            'For cases already actionable early, preserve the early entry. Dense +1/+2/+3/+4/+5-second survivorship is fallback-only for cases not sufficiently actionable at the earliest validated entry.',
            'Rows that become knowable only after endpoint+5 remain research candidates for alternative later-entry windows if enough causal runway and cost-adjusted edge remain.',
            'Final chain depth, realized final duration and future path shape may never leak into an earlier checkpoint.'
        ],
        'hard_failures':hard,
        'promotion_performed':False,
        'protected_mutations':{'detector':False,'canonical_rows':False,'phase1':False,'phase2':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}
    }
    if hard:raise SystemExit(hard[:3])
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'headline_h5':result['headline_h5'],'exact_depth_counts':result['exact_depth_counts']},indent=2))
if __name__=='__main__':main()
