#!/usr/bin/env python3
"""Scratch-only Frankie reveal-first packet for NG exhaustion families.

No Frankie/brain/schema/role/play mutation. Family labels are frozen from t<=0 roll-20
dipole geometry only. The revealed half contains all three substantive families together,
with full corresponding price legs and all available causal microstructure context.
The held-out half is identified only in a sealed manifest and is NOT emitted here.
"""
from __future__ import annotations
import hashlib, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.preprocessing import RobustScaler
import databento as db

import ng_exhaustion_family_quantify_v2_20260816 as fam
from ng_dipole_native_shape_audit import event_rows, flow_series
from ng_dipole_runway_audit import load_day, zigzag_legs

ROLL=20; PRE=60; POST=60; SEED='NG_EXHAUSTION_REVEAL_20260816_V1'; MIN_FAMILY=20
MBO_MAP={
 '20250923':'/tmp/ng_mbo_ngv25_20250923.dbn.zst',
 '20250930':'/tmp/ng_mbo_ngx25_20250930.dbn.zst',
 '20251001':'/tmp/ng_mbo_ngx25_20251001.dbn.zst',
}

def side_name(x):
    return str(getattr(x,'name',getattr(x,'value',x))).upper()

def act_name(x):
    return str(getattr(x,'value',x)).upper()

def mbo_seconds(path):
    out=defaultdict(lambda: defaultdict(float))
    if not Path(path).is_file(): return {}
    for r in db.DBNStore.from_file(path):
        if type(r).__name__!='MBOMsg': continue
        sec=int(int(r.ts_event)//1_000_000_000)%86400
        a=act_name(r.action); s=side_name(r.side); sz=float(getattr(r,'size',0) or 0)
        k={'A':'add','C':'cancel','M':'modify','T':'trade','F':'fill','R':'clear'}.get(a,a.lower())
        out[sec][f'{k}_events']+=1
        out[sec][f'{k}_size']+=sz
        if s in ('B','BID','BUY'):
            out[sec][f'{k}_bid_size']+=sz
        elif s in ('A','ASK','SELL'):
            out[sec][f'{k}_ask_size']+=sz
    return {k:dict(v) for k,v in out.items()}

def curve(vals,t0,lo,hi):
    z=[]
    for dt in range(lo,hi+1):
        i=t0+dt
        v=vals[i] if 0<=i<len(vals) else float('nan')
        z.append(None if not math.isfinite(float(v)) else float(v))
    return z

def mbo_curve(mbo,t0,lo,hi):
    keys=['add_events','add_size','add_bid_size','add_ask_size','cancel_events','cancel_size','cancel_bid_size','cancel_ask_size','modify_events','modify_size','trade_events','trade_size','trade_bid_size','trade_ask_size','fill_events','fill_size']
    return {k:[float(mbo.get(t0+dt,{}).get(k,0.0)) for dt in range(lo,hi+1)] for k in keys}

def containing_or_near(legs,t0):
    inside=[x for x in legs if x['start']<=t0<=x['end']]
    if inside: return min(inside,key=lambda x:x['end']-x['start'])
    if not legs: return None
    x=min(legs,key=lambda y:abs(y['start']-t0))
    return x if abs(x['start']-t0)<=15 else None

def event_id(r):
    return f"{r['day']}-{int(r['flip_s']):05d}-{int(r['dipole_polarity']):+d}"

def split_key(r,label):
    s=f"{SEED}|{label}|{event_id(r)}".encode()
    return hashlib.sha256(s).hexdigest()

def main(paths):
    days={}; rows=[]
    for p in paths:
        d=load_day(p); days[d.day]=d; rows.extend(event_rows(d,ROLL))
    raw=np.vstack([fam.feature(r) for r in rows])
    sc=RobustScaler(quantile_range=(20,80)).fit(raw); X=sc.transform(raw)
    _,lab4,_,_=fam.fit_balanced(X,4)
    counts=Counter(map(int,lab4)); singles=[c for c,n in counts.items() if n==1]
    if len(singles)!=1: raise SystemExit(f'expected exactly one K4 singleton, got {counts}')
    keep=np.array([int(z)!=singles[0] for z in lab4],dtype=bool)
    rows2=[r for r,k in zip(rows,keep) if k]
    raw2=np.vstack([fam.feature(r) for r in rows2])
    sc2=RobustScaler(quantile_range=(20,80)).fit(raw2); X2=sc2.transform(raw2)
    centers,lab3,_,_=fam.fit_balanced(X2,3)
    lab3,centers,_=fam.deterministic_order(rows2,lab3,centers)
    family_names={0:'A',1:'B',2:'C'}
    fam_counts=Counter(map(int,lab3)); byday=defaultdict(Counter)
    for r,z in zip(rows2,lab3): byday[int(z)][r['day']]+=1
    if any(fam_counts[c]<MIN_FAMILY for c in range(3)): raise SystemExit(f'non-substantive family: {fam_counts}')
    if any(any(byday[c][d]==0 for d in days) for c in range(3)): raise SystemExit(f'family missing day: {dict(byday)}')

    reveal_ids=set(); holdout_hashes=[]; split_counts=defaultdict(lambda:{'reveal':0,'holdout':0})
    strata=defaultdict(list)
    for i,(r,z) in enumerate(zip(rows2,lab3)): strata[(int(z),r['day'])].append((split_key(r,int(z)),i))
    for key,items in strata.items():
        items.sort(); n=len(items); nrev=(n+1)//2
        for j,(_,i) in enumerate(items):
            if j<nrev:
                reveal_ids.add(i); split_counts[key]['reveal']+=1
            else:
                holdout_hashes.append(hashlib.sha256(event_id(rows2[i]).encode()).hexdigest()); split_counts[key]['holdout']+=1

    mbo={d:mbo_seconds(p) for d,p in MBO_MAP.items()}
    pricelegs={d:{th:zigzag_legs(day.price,th) for th in (2,3,5,8,13)} for d,day in days.items()}
    flow60={d:flow_series(day,60) for d,day in days.items()}
    records=[]
    for i,(r,z) in enumerate(zip(rows2,lab3)):
        if i not in reveal_ids: continue
        d=days[r['day']]; t0=int(r['flip_s']); primary=containing_or_near(pricelegs[r['day']][3],t0)
        if primary:
            lo=max(-300,int(primary['start'])-t0-60); hi=min(900,int(primary['end'])-t0+60)
        else:
            lo=-60; hi=300
        p=curve(d.price,t0,lo,hi); p0=d.price[t0] if math.isfinite(d.price[t0]) else next((x for x in p if x is not None),None)
        norm=[None if x is None or p0 is None else (x-p0)/0.001 for x in p]
        leginfo={}
        for th in (2,3,5,8,13):
            L=containing_or_near(pricelegs[r['day']][th],t0)
            leginfo[str(th)] = None if L is None else {'start_offset_s':int(L['start'])-t0,'end_offset_s':int(L['end'])-t0,'duration_s':int(L['duration']),'direction':int(L['dir']),'ticks':float(L['ticks'])}
        rec={
          'event_id':event_id(r),'family':family_names[int(z)],'day':r['day'],'t0_second_utc':t0,'dipole_polarity':int(r['dipole_polarity']),
          'dipole_roll20_oriented_t_minus60_to_plus60':r['pre_raw']+r['post_raw'][1:],
          'dipole_roll60_raw_t_minus60_to_plus60':curve(flow60[r['day']],t0,-60,60),
          'book_10level_imbalance_t_minus60_to_plus60':curve(d.book,t0,-60,60),
          'aggressor_buy_volume_t_minus60_to_plus60':curve(d.buy_vol,t0,-60,60),
          'aggressor_sell_volume_t_minus60_to_plus60':curve(d.sell_vol,t0,-60,60),
          'price_curve_offsets_s':[lo,hi],'price_curve_ticks_from_t0':norm,
          'attached_zigzag_legs_by_reversal_ticks':leginfo,
          'post_exhaustion':{'t50_s':r['exh_t50_s'],'t25_s':r['exh_t25_s'],'t10_s':r['exh_t10_s'],'zero_s':r['exh_zero_s']},
          'mbo_status':'MATCHED_CONTRACT_MBO' if r['day'] in mbo else 'UNAVAILABLE_MBP10_ONLY',
          'mbo_t_minus60_to_plus60':mbo_curve(mbo.get(r['day'],{}),t0,-60,60) if r['day'] in mbo else None,
        }
        records.append(rec)
    manifest={
      'protocol':'REVEAL_FIRST_ONLY','seed_tag':SEED,'family_discovery':'t<=0 roll20 dipole geometry only; price/post excluded',
      'removed_pathological_singleton_n':1,'substantive_family_counts':{family_names[c]:fam_counts[c] for c in range(3)},
      'family_by_day':{family_names[c]:dict(byday[c]) for c in range(3)},
      'revealed_n':len(records),'heldout_n':len(rows2)-len(records),
      'split_by_family_day':{f"{family_names[c]}:{d}":v for (c,d),v in split_counts.items()},
      'revealed_contains_all_three_families_together':True,
      'revealed_contains_full_price_leg_context':True,
      'mbo_exact_contract_days':{'20250923':'NGV25','20250930':'NGX25','20251001':'NGX25'},
      'mbo_unavailable_days':['20250717'],
      'holdout_event_ids_exposed':False,
      'holdout_integrity_hashes_sha256':sorted(holdout_hashes),
      'brain_or_frankie_mutated':False,
    }
    Path('ng_frankie_reveal_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    Path('ng_frankie_reveal_records.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
    prompt='''You are Frankie in a scratch research analysis. This is REVEAL FIRST, not a forecast. You are shown the revealed 50% of each of three independently frozen pre-dipole families together with their full corresponding price legs and all available microstructure. Do not assume any family means short/medium/long. Discover what repeatable relationships, subfamilies, timing structures, failure modes, or price-leg characteristics the evidence itself supports. Compare all three families against one another. Use MBO where present and explicitly distinguish July MBP-10-only evidence. Do not change the brain/schema/roles/plays/datapoints. Produce a compact research memo containing: (1) independent observations, (2) family-by-family price relationship hypotheses, (3) within-family post-exhaustion states if present, (4) microstructure clues that improve separation, (5) exact predictions you would make later when price is withheld, and (6) falsifiers/uncertainties. Do not inspect or infer the sealed holdout.'''
    Path('ng_frankie_reveal_prompt.txt').write_text(prompt+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':
    main(sys.argv[1:])
