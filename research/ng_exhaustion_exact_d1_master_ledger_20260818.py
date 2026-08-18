#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import ng_exhaustion_exact_d1_agents_v2_20260818 as core


def finite(x):
    return core.finite(x)


def safe_mean(xs):
    a=[float(x) for x in xs if finite(x)]
    return sum(a)/len(a) if a else None


def support_grade(n):
    if n >= 100:
        return 'HIGH_SUPPORT'
    if n >= 30:
        return 'MODERATE_SUPPORT'
    if n >= 10:
        return 'LOW_SUPPORT'
    return 'VERY_LOW_SUPPORT_PRESERVED'


def row_record(r):
    raw=r.get('desc_ret60_from5')
    rec={
        'week':r['week'],
        'd1_block':r['block'],
        'origin_sequence_index':r['origin_seq'],
        'origin_event_id':r['origin_event_id'],
        'descendant_event_id':r['desc_event_id'],
        'elapsed_origin_to_descendant_seconds':r['elapsed'],
        'duration_family':r.get('duration_family'),
        'origin_wall_to_descendant_seconds':r.get('origin_wall_to_desc_t0'),
        'pair':r.get('pair'),
        'origin_state':r.get('origin_code'),
        'descendant_state':r.get('desc_code'),
        'older_causal_state':r.get('older_code'),
        'origin_family':r.get('origin_family'),
        'origin_a_state':r.get('origin_a_state'),
        'descendant_child_depth':r.get('child_depth'),
        'descendant_child_elapsed_seconds':r.get('child_elapsed'),
        'descendant_reference_return_with_descendant_polarity_ticks':raw,
        'descendant_reference_return_against_descendant_polarity_ticks':None if not finite(raw) else -float(raw),
        'with_descendant_net_0_5_ticks':None if not finite(raw) else float(raw)-0.5,
        'with_descendant_net_1_ticks':None if not finite(raw) else float(raw)-1.0,
        'with_descendant_net_2_ticks':None if not finite(raw) else float(raw)-2.0,
        'against_descendant_net_0_5_ticks':None if not finite(raw) else -float(raw)-0.5,
        'against_descendant_net_1_ticks':None if not finite(raw) else -float(raw)-1.0,
        'against_descendant_net_2_ticks':None if not finite(raw) else -float(raw)-2.0,
        'descendant_h60_mfe_ticks':r.get('desc_h',{}).get('60',{}).get('mfe_ticks'),
        'descendant_h60_mae_ticks':r.get('desc_h',{}).get('60',{}).get('mae_ticks'),
        'preserved':True,
    }
    return rec


def group_summary(rows, fields):
    d=defaultdict(list)
    for r in rows:
        key=tuple(r.get(f) for f in fields)
        d[key].append(r)
    out=[]
    for key,rr in d.items():
        vals=[x['descendant_reference_return_with_descendant_polarity_ticks'] for x in rr if finite(x.get('descendant_reference_return_with_descendant_polarity_ticks'))]
        byblock={}
        for b in ('train','era45','conf','held'):
            q=[x for x in rr if x['d1_block']==b]
            v=[x['descendant_reference_return_with_descendant_polarity_ticks'] for x in q if finite(x.get('descendant_reference_return_with_descendant_polarity_ticks'))]
            byblock[b]={
                'n':len(q),
                'with_descendant_mean_ticks':safe_mean(v),
                'against_descendant_mean_ticks':safe_mean([-float(z) for z in v]),
                'elapsed_seconds':core.summary([x['elapsed_origin_to_descendant_seconds'] for x in q]),
            }
        out.append({
            'fields':list(fields),
            'key':{f:v for f,v in zip(fields,key)},
            'n':len(rr),
            'support_grade':support_grade(len(rr)),
            'elapsed_seconds':core.summary([x['elapsed_origin_to_descendant_seconds'] for x in rr]),
            'origin_wall_to_descendant_seconds':core.summary([x['origin_wall_to_descendant_seconds'] for x in rr]),
            'with_descendant_mean_ticks':safe_mean(vals),
            'against_descendant_mean_ticks':safe_mean([-float(z) for z in vals]),
            'blocks':byblock,
            'preserved_even_if_low_support':True,
        })
    out.sort(key=lambda z:z['n'],reverse=True)
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True)
    ap.add_argument('--held',required=True)
    ap.add_argument('--base-lineage',required=True)
    ap.add_argument('--held-lineage',required=True)
    ap.add_argument('--summary',required=True)
    ap.add_argument('--out-summary',required=True)
    ap.add_argument('--out-ledger',required=True)
    a=ap.parse_args()

    weeks=json.load(open(a.summary))['weeks']
    events=core.load_events(a.base,a.held)
    lineage=core.load_lineage(a.base_lineage,a.held_lineage)
    d1,model=core.d1_records(events,lineage,weeks)
    rows=[row_record(r) for r in d1]

    with gzip.open(a.out_ledger,'wt') as f:
        for r in rows:
            f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')

    result={
        'status':'EXACT_D1_MASTER_LEDGER_COMPLETE',
        'preserve_all_policy':True,
        'exact_d1_n':len(rows),
        'duration_model':{
            'selected_components':model['k'],
            'centers_seconds':model['centers'],
            'labels':model['labels'],
            'fit_block':'D1_DISCOVERY_OOT_BASE_WEEKS_18_35',
        },
        'elapsed_seconds':core.summary([r['elapsed_origin_to_descendant_seconds'] for r in rows]),
        'origin_wall_to_descendant_seconds':core.summary([r['origin_wall_to_descendant_seconds'] for r in rows]),
        'block_counts':dict(Counter(r['d1_block'] for r in rows)),
        'duration_family_counts':dict(Counter(r['duration_family'] for r in rows)),
        'pair_counts':dict(Counter(r['pair'] for r in rows)),
        'groups':{
            'pair':group_summary(rows,('pair',)),
            'duration_family':group_summary(rows,('duration_family',)),
            'pair_x_duration_family':group_summary(rows,('pair','duration_family')),
            'pair_x_older_state':group_summary(rows,('pair','older_causal_state')),
            'pair_x_duration_x_older_state':group_summary(rows,('pair','duration_family','older_causal_state')),
        },
        'ledger_file':a.out_ledger,
        'interpretation':'Every valid exact-D1 instance is retained. Profitability, duration, support and path shape annotate/rank the population but never define membership.',
        'promotion_performed':False,
        'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
    }
    Path(a.out_summary).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    main()
