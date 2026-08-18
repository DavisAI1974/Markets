#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

BLOCKS=('train','era45','conf','held')
VALIDATION=('era45','conf','held')


def finite(x):
    try:return math.isfinite(float(x))
    except Exception:return False

def mean(xs):
    a=[float(x) for x in xs if finite(x)]
    return sum(a)/len(a) if a else None
def median(xs):
    a=[float(x) for x in xs if finite(x)]
    return statistics.median(a) if a else None
def quantile(xs,q):
    a=sorted(float(x) for x in xs if finite(x))
    if not a:return None
    z=(len(a)-1)*q;i=int(math.floor(z));j=int(math.ceil(z))
    return a[i] if i==j else a[i]*(j-z)+a[j]*(z-i)
def support(n):
    if n>=100:return 'HIGH_SUPPORT'
    if n>=30:return 'MODERATE_SUPPORT'
    if n>=10:return 'LOW_SUPPORT'
    return 'VERY_LOW_SUPPORT_PRESERVED'
def load(path):
    with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
def key_for(r,fields):return tuple(r.get(f) for f in fields)
def block_stats(rows,ori):
    vals=[ori*float(r['descendant_reference_return_with_descendant_polarity_ticks']) for r in rows if finite(r.get('descendant_reference_return_with_descendant_polarity_ticks'))]
    return {
      'n':len(rows),'scored_n':len(vals),'gross_mean_ticks':mean(vals),'gross_median_ticks':median(vals),
      'net_0_5_mean_ticks':mean([v-.5 for v in vals]),'net_1_mean_ticks':mean([v-1 for v in vals]),'net_2_mean_ticks':mean([v-2 for v in vals]),
      'positive_gross_rate':sum(v>0 for v in vals)/len(vals) if vals else None,
      'elapsed_median_seconds':median([r.get('elapsed_origin_to_descendant_seconds') for r in rows]),
      'elapsed_p95_seconds':quantile([r.get('elapsed_origin_to_descendant_seconds') for r in rows],.95),
      'elapsed_max_seconds':max([r.get('elapsed_origin_to_descendant_seconds') for r in rows if finite(r.get('elapsed_origin_to_descendant_seconds'))],default=None),
    }
def rank_group(rows,fields):
    D=defaultdict(list)
    for r in rows:D[key_for(r,fields)].append(r)
    out=[]
    for key,R in D.items():
        tr=[r for r in R if r['d1_block']=='train' and finite(r.get('descendant_reference_return_with_descendant_polarity_ticks'))]
        tm=mean([r['descendant_reference_return_with_descendant_polarity_ticks'] for r in tr])
        ori=None if tm is None else (1 if tm>=0 else -1)
        rec={
          'fields':list(fields),'key':{f:v for f,v in zip(fields,key)},'n':len(R),'support_grade':support(len(R)),
          'discovery_scored_n':len(tr),'discovery_mean_with_descendant_ticks':tm,
          'orientation':None if ori is None else ('WITH_DESCENDANT_POLARITY' if ori==1 else 'AGAINST_DESCENDANT_POLARITY'),
          'causal_rank_status':'RANKABLE_DISCOVERY_DIRECTION_FIXED' if ori is not None else 'PRESERVED_NO_DISCOVERY_DIRECTION',
          'blocks':{},'preserved':True,
        }
        if ori is not None:
            for b in BLOCKS:rec['blocks'][b]=block_stats([r for r in R if r['d1_block']==b],ori)
            vg=[]
            for b in VALIDATION:
                vg.extend([ori*float(r['descendant_reference_return_with_descendant_polarity_ticks']) for r in R if r['d1_block']==b and finite(r.get('descendant_reference_return_with_descendant_polarity_ticks'))])
            rec['validation_gross_mean_ticks']=mean(vg)
            rec['validation_net_0_5_mean_ticks']=mean([v-.5 for v in vg])
            rec['validation_net_1_mean_ticks']=mean([v-1 for v in vg])
            rec['validation_net_2_mean_ticks']=mean([v-2 for v in vg])
            per=[rec['blocks'][b]['gross_mean_ticks'] for b in VALIDATION if rec['blocks'][b]['gross_mean_ticks'] is not None]
            rec['worst_validation_block_gross_mean_ticks']=min(per) if per else None
        out.append(rec)
    rankable=[r for r in out if finite(r.get('validation_gross_mean_ticks'))]
    rankable.sort(key=lambda r:(r['validation_gross_mean_ticks'],r['n']),reverse=True)
    n=len(rankable)
    for i,r in enumerate(rankable):
        r['relative_profit_rank']=i+1
        pct=(i+1)/n if n else 1
        r['relative_profitability_tier']='TOP_10_PERCENT' if pct<=.10 else 'UPPER_QUARTILE' if pct<=.25 else 'MIDDLE_50_PERCENT' if pct<=.75 else 'LOWER_QUARTILE'
    unranked=[r for r in out if not finite(r.get('validation_gross_mean_ticks'))]
    return rankable+unranked

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    rows=load(a.ledger)
    groups={
      'pair':rank_group(rows,('pair',)),
      'duration_family':rank_group(rows,('duration_family',)),
      'pair_x_duration':rank_group(rows,('pair','duration_family')),
      'pair_x_older_state':rank_group(rows,('pair','older_causal_state')),
      'pair_x_duration_x_older_state':rank_group(rows,('pair','duration_family','older_causal_state')),
    }
    res={
      'status':'EXACT_D1_PRESERVE_ALL_RELATIVE_PROFIT_RANK_COMPLETE','exact_d1_n':len(rows),'preserve_all_policy':True,
      'reference_lens':'Common descendant endpoint+5 to endpoint+60 return, with orientation frozen from the D1 discovery/OOT block when available. This is a comparison lens, not a rejection rule or proof that another D1 monetization path is absent.',
      'groups':groups,'promotion_performed':False,
      'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}
    }
    Path(a.out).write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
