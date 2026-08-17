#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, json, math, os, sys
from collections import Counter, defaultdict, OrderedDict
from pathlib import Path
import numpy as np
from sklearn.preprocessing import RobustScaler
import databento as db

HERE=Path(__file__).resolve().parent
KALSHI=HERE/'kalshi'
if str(KALSHI) not in sys.path: sys.path.insert(0,str(KALSHI))
import brain_view
import ng_exhaustion_family_quantify_v2_20260816 as fam
from ng_dipole_native_shape_audit import event_rows, flow_series
from ng_dipole_runway_audit import load_day

ROLL=20
SEED='NG_EXHAUSTION_REVEAL_20260816_V1'
TARGET_DAYS=('20250717','20250923','20250930','20251001')
MBO_MAP={'20250923':'/tmp/ng_mbo_ngv25_20250923.dbn.zst','20250930':'/tmp/ng_mbo_ngx25_20250930.dbn.zst','20251001':'/tmp/ng_mbo_ngx25_20251001.dbn.zst'}
CLASSIFIER=Path('research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json')
CLASSIFIER_SHA256='698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9'
FORBIDDEN=('zigzag','duration','displacement','pnl','actual','ticks','pivot','midpoint','bid_price','ask_price')

def ev_id(r): return f"{r['day']}-{int(r['flip_s']):05d}-{int(r['dipole_polarity']):+d}"
def split_key(r,z): return hashlib.sha256(f"{SEED}|{z}|{ev_id(r)}".encode()).hexdigest()
def blind_id(r): return 'BL-'+hashlib.sha256(ev_id(r).encode()).hexdigest()[:20]
def side(x): return str(getattr(x,'name',getattr(x,'value',x))).upper()
def action(x): return str(getattr(x,'value',x)).upper()

def mbo_seconds(path):
    out=defaultdict(lambda: defaultdict(float))
    if not Path(path).is_file(): return {}
    for r in db.DBNStore.from_file(path):
        if type(r).__name__!='MBOMsg': continue
        sec=int(int(r.ts_event)//1_000_000_000)%86400
        a=action(r.action); s=side(r.side); sz=float(getattr(r,'size',0) or 0)
        k={'A':'add','C':'cancel','M':'modify','T':'trade','F':'fill','R':'clear'}.get(a,a.lower())
        out[sec][f'{k}_events']+=1; out[sec][f'{k}_size']+=sz
        if s in ('B','BID','BUY'): out[sec][f'{k}_bid_size']+=sz
        elif s in ('A','ASK','SELL'): out[sec][f'{k}_ask_size']+=sz
    return {k:dict(v) for k,v in out.items()}

def vec(vals,t0):
    z=[]
    for dt in range(-60,61):
        i=t0+dt; v=vals[i] if 0<=i<len(vals) else float('nan')
        z.append(None if not math.isfinite(float(v)) else float(v))
    return z

def mbo_vec(mbo,t0):
    keys=['add_events','add_size','add_bid_size','add_ask_size','cancel_events','cancel_size','cancel_bid_size','cancel_ask_size','modify_events','modify_size','trade_events','trade_size','trade_bid_size','trade_ask_size','fill_events','fill_size']
    return {k:[float(mbo.get(t0+dt,{}).get(k,0.0)) for dt in range(-60,61)] for k in keys}

def target_tokens():
    out=set()
    for d in TARGET_DAYS:
        y,m,dd=d[:4],d[4:6],d[6:8]
        out.update((d,f'{y}-{m}-{dd}',f'{m}{dd}',f'{m}/{dd}'))
    return out

def redact(obj,toks,c):
    if isinstance(obj,dict):
        out=OrderedDict()
        for k,v in obj.items():
            if any(t in str(k) for t in toks): c[0]+=1; out[k]='[REDACTED_TARGET_DAY]'
            else: out[k]=redact(v,toks,c)
        return out
    if isinstance(obj,list): return [redact(v,toks,c) for v in obj]
    if isinstance(obj,str) and any(t in obj for t in toks): c[0]+=1; return '[REDACTED_TARGET_DAY]'
    return obj

def scan_keys(x,path=''):
    bad=[]
    if isinstance(x,dict):
        for k,v in x.items():
            p=f'{path}.{k}' if path else str(k); lk=str(k).lower()
            if 'price' in lk and str(k)!='causal_price_anchor': bad.append(p)
            if any(t in lk for t in FORBIDDEN): bad.append(p)
            bad.extend(scan_keys(v,p))
    elif isinstance(x,list):
        for i,v in enumerate(x[:2]): bad.extend(scan_keys(v,f'{path}[{i}]'))
    return bad

def load_frozen_classifier():
    if not CLASSIFIER.is_file(): raise SystemExit('frozen A post-state classifier missing')
    got=hashlib.sha256(CLASSIFIER.read_bytes()).hexdigest()
    if got!=CLASSIFIER_SHA256: raise SystemExit(f'frozen classifier digest drift {got}')
    c=json.loads(CLASSIFIER.read_text())
    ic=c.get('input_contract',{})
    if ic.get('field')!='dipole_roll20_oriented_t_minus60_to_plus60' or ic.get('slice')!='[60:]' or ic.get('feature_count')!=61:
        raise SystemExit('frozen classifier input contract drift')
    return c, np.asarray(c['cluster_mapping']['A-fast-collapse']['centroid'],float), np.asarray(c['cluster_mapping']['A-persistent']['centroid'],float)

def classify_a(curve,c0,c1):
    x=np.asarray(curve[60:],float)
    if len(x)!=61 or not np.all(np.isfinite(x)) or abs(float(x[0]))<=1e-15:
        raise SystemExit('A classifier normalization invariant failure')
    x=x/float(x[0])
    d0=float(np.linalg.norm(x-c0)); d1=float(np.linalg.norm(x-c1))
    if d0==d1: raise SystemExit('A classifier exact tie with no frozen custom tie rule')
    return ('A-fast-collapse' if d0<d1 else 'A-persistent'), d0, d1

def main(paths):
    memo=Path('research/FRANKIE_NG_EXHAUSTION_REVEAL_MEMO_20260816.md')
    if not memo.is_file(): raise SystemExit('frozen reveal memo missing')
    memo_sha=hashlib.sha256(memo.read_bytes()).hexdigest()
    classifier,c0,c1=load_frozen_classifier()
    days={}; rows=[]
    for p in paths:
        d=load_day(p); days[d.day]=d; rows.extend(event_rows(d,ROLL))
    if tuple(sorted(days))!=TARGET_DAYS: raise SystemExit('target-day drift')
    X0=np.vstack([fam.feature(r) for r in rows]); X=RobustScaler(quantile_range=(20,80)).fit_transform(X0)
    _,l4,_,_=fam.fit_balanced(X,4); cnt=Counter(map(int,l4)); one=[c for c,n in cnt.items() if n==1]
    if len(one)!=1: raise SystemExit(f'singleton invariant {cnt}')
    rows=[r for r,z in zip(rows,l4) if int(z)!=one[0]]
    X0=np.vstack([fam.feature(r) for r in rows]); X=RobustScaler(quantile_range=(20,80)).fit_transform(X0)
    centers,l3,_,_=fam.fit_balanced(X,3); l3,centers,_=fam.deterministic_order(rows,l3,centers)
    names={0:'A',1:'B',2:'C'}
    strata=defaultdict(list)
    for i,(r,z) in enumerate(zip(rows,l3)): strata[(int(z),r['day'])].append((split_key(r,int(z)),i))
    hold=set()
    for items in strata.values():
        items.sort(); nrev=(len(items)+1)//2
        hold.update(i for _,i in items[nrev:])
    if len(hold)!=1711: raise SystemExit(f'holdout split drift {len(hold)}')
    mbo={d:mbo_seconds(p) for d,p in MBO_MAP.items()}; f60={d:flow_series(x,60) for d,x in days.items()}
    out=[]; astate=Counter()
    for i,(r,z) in enumerate(zip(rows,l3)):
        if i not in hold: continue
        d=days[r['day']]; t=int(r['flip_s']); fam_name=names[int(z)]
        anchor=float(d.price[t]) if 0<=t<len(d.price) else float('nan')
        if not math.isfinite(anchor) or anchor<=0: raise SystemExit(f'causal t0 anchor missing {ev_id(r)}')
        curve=r['pre_raw']+r['post_raw'][1:]
        if fam_name=='A':
            lab,d0,d1=classify_a(curve,c0,c1); astate[lab]+=1
            post_state={'status':'FROZEN_A_NEAREST_CENTROID','label':lab,'distance_fast_collapse':d0,'distance_persistent':d1}
        else:
            post_state={'status':'NO_FROZEN_BC_SUBTYPE_ASSIGNMENT_RULE','label':None}
        out.append({'blind_id':blind_id(r),'family':fam_name,'day':r['day'],'t0_second_utc':t,'dipole_polarity':int(r['dipole_polarity']),
          'causal_price_anchor':{'value':anchor,'asof_second_utc':t,'source':'authoritative continuous MBP10 last trade carried forward through t0','semantics':'single causal origin only; no t>t0 trade/bid/ask/midpoint price served'},
          'frozen_post_state_assignment':post_state,
          'dipole_roll20_oriented_t_minus60_to_plus60':curve,
          'dipole_roll60_raw_t_minus60_to_plus60':vec(f60[r['day']],t),
          'book_10level_imbalance_t_minus60_to_plus60':vec(d.book,t),
          'aggressor_buy_volume_t_minus60_to_plus60':vec(d.buy_vol,t),
          'aggressor_sell_volume_t_minus60_to_plus60':vec(d.sell_vol,t),
          'post_exhaustion_dipole_only':{'t50_s':r['exh_t50_s'],'t25_s':r['exh_t25_s'],'t10_s':r['exh_t10_s'],'zero_s':r['exh_zero_s']},
          'mbo_status':'MATCHED_CONTRACT_MBO' if r['day'] in mbo else 'UNAVAILABLE_MBP10_ONLY',
          'mbo_orderflow_t_minus60_to_plus60':mbo_vec(mbo.get(r['day'],{}),t) if r['day'] in mbo else None})
    if sum(astate.values())!=1616: raise SystemExit(f'A state coverage drift {astate}')
    for q in out:
        a=q['causal_price_anchor']
        if a['asof_second_utc']!=q['t0_second_utc'] or not math.isfinite(float(a['value'])): raise SystemExit('causal price-anchor invariant failure')
    bad=scan_keys(out)
    if bad: raise SystemExit(f'forbidden blind fields {bad[:10]}')
    toks=target_tokens(); c=[0]; brain=redact(copy.deepcopy(brain_view.load()),toks,c)
    serialized=json.dumps(brain,separators=(',',':'))
    leaks=[t for t in toks if t in serialized]
    if leaks: raise SystemExit(f'target-day brain leak {leaks}')
    brain['_ng_exhaustion_blind_contract']={'source_brain_mutated':False,'served_copy_only':True,'target_day_redactions':c[0],'reveal_findings_not_taught_into_brain':True,'frozen_reveal_memo_sha256':memo_sha,'causal_t0_price_anchor_only':True,'future_price_outcomes_withheld':True,'frozen_a_classifier_sha256':CLASSIFIER_SHA256}
    Path('ng_frankie_blind_records.json').write_text(json.dumps(out,separators=(',',':'))+'\n')
    Path('ng_frankie_blind_full_brain_redacted.json').write_text(json.dumps(brain,separators=(',',':'))+'\n')
    man={'protocol':'BLIND_AFTER_FROZEN_REVEAL_WITH_CAUSAL_T0_PRICE_ANCHOR','blind_n':len(out),'family_counts':dict(Counter(x['family'] for x in out)),'a_post_state_counts':dict(astate),'a_classifier_sha256':CLASSIFIER_SHA256,'a_classifier_fit_n':classifier['provenance']['fit_n'],'bc_post_state_subtype_rule':'NONE_FROZEN; do not invent or refit; use frozen family/scale hypotheses only','causal_price_anchor_served':True,'causal_price_anchor_definition':'authoritative continuous MBP10 last trade carried forward through t0 only','future_price_or_price_bearing_window_served':False,'full_brain_served':True,'source_brain_mutated':False,'target_day_brain_redactions':c[0],'blind_record_outcome_wall_scan':'PASS','target_day_brain_leak_scan':'PASS','reveal_memo_sha256':memo_sha}
    Path('ng_frankie_blind_manifest.json').write_text(json.dumps(man,indent=2)+'\n')
    Path('ng_frankie_blind_prompt.txt').write_text('Carry the frozen reveal memo and frozen A post-state classifier forward exactly. Analyze every held-out blind_id using the supplied dipole/exhaustion, book, aggressor-flow, MBO evidence, the single causal t0 price anchor, and the read-only target-day-redacted full brain. The t0 anchor is only an absolute-price origin; no t>t0 price is available. For Family A, use the supplied frozen nearest-centroid state assignment exactly. No frozen deterministic B/C persistent-collapse subtype classifier exists in the legal packet, so do not invent, fit, or infer one; apply the frozen B/C family and scale hypotheses with appropriately low confidence. Predict the missing price-leg duration/band at 3t/5t/8t (13t optional), magnitude/tick scale, local-vs-broader alignment/continuation/reversal/failure, state/family interpretation and confidence, frozen reveal rules used, brain concepts that materially change the call, early-pre-t0 precursor agreement, and uncertainty/falsifier. Do not inspect or reconstruct held-out future price, and do not alter Frankie or the brain/schema/roles/plays/datapoints/workflow. Freeze all predictions before any scoring reveal.\n')
    print(json.dumps(man,indent=2))
if __name__=='__main__': main(sys.argv[1:])
