#!/usr/bin/env python3
"""Freeze Frankie's NG exhaustion blind single-best price curves.

Scratch experiment only. Consumes only the guarded blind packet: non-price dipole/book/flow/MBO,
the single causal t0 price anchor, frozen A post-state assignment, and target-day-redacted brain.
It never opens or materializes held-out future price/outcome data.
"""
from __future__ import annotations
import gzip, hashlib, json, math
from collections import Counter
from pathlib import Path
import numpy as np

TICK=0.001
SCHEMA=Path('research/FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_SCHEMA_FROZEN_20260816.json')
RECORDS=Path('ng_frankie_blind_records.json')
BRAIN=Path('ng_frankie_blind_full_brain_redacted.json')
INPUT_MANIFEST=Path('ng_frankie_blind_manifest.json')
OUT=Path('research/blind_freeze/ng_exhaustion_20260816')
A_DURS={'A-fast-collapse':{'3t':358,'5t':993,'8t':1802,'13t':4386},'A-persistent':{'3t':700,'5t':1802,'8t':3455,'13t':6836}}
B_DURS={'3t':353,'5t':995,'8t':1615,'13t':4543}
C_DURS={'3t':377,'5t':1159,'8t':1713,'13t':4320}
BRAIN_IDS=('direction.flow_nowcast','shape.grind_vs_spike','exit.recruitment_reversal','timing.subsecond_reversal_exhaustion')

def clip(x,a,b): return max(a,min(b,x))
def arr(v): return np.asarray([np.nan if x is None else float(x) for x in v],dtype=float)

def oriented_flow(r,start,end):
    b=arr(r['aggressor_buy_volume_t_minus60_to_plus60']); s=arr(r['aggressor_sell_volume_t_minus60_to_plus60'])
    sl=slice(start+60,end+61); bb=float(np.nansum(b[sl])); ss=float(np.nansum(s[sl])); tot=bb+ss
    raw=(bb-ss)/tot if tot>0 else 0.0
    return int(r['dipole_polarity'])*raw

def oriented_book(r,start,end):
    a=arr(r['book_10level_imbalance_t_minus60_to_plus60'])[start+60:end+61]; a=a[np.isfinite(a)]
    return int(r['dipole_polarity'])*(float(a.mean()) if len(a) else 0.0)

def mbo_oriented(r,start,end):
    m=r.get('mbo_orderflow_t_minus60_to_plus60')
    if not m: return None
    bid=arr(m.get('trade_bid_size',[0]*121))[start+60:end+61].sum(); ask=arr(m.get('trade_ask_size',[0]*121))[start+60:end+61].sum(); tot=float(bid+ask)
    return int(r['dipole_polarity'])*(float(bid-ask)/tot if tot else 0.0)

def support(r):
    f20=oriented_flow(r,1,20); f60=oriented_flow(r,21,60); book=oriented_book(r,1,60); mbo=mbo_oriented(r,1,20)
    mw=0.18 if mbo is not None else 0.0; raw=0.38*f20+0.28*f60+0.16*clip(book*3,-1,1)+(mw*(mbo or 0.0)); den=0.82+mw
    score=clip(raw/den,-1,1)
    return score,{'flow_1_20':f20,'flow_21_60':f60,'book_1_60':book,'mbo_1_20':mbo}

def exhaustion_time(r):
    e=r['post_exhaustion_dipole_only']
    for k in ('zero_s','t10_s','t25_s','t50_s'):
        if e.get(k) is not None: return int(e[k])
    x=arr(r['dipole_roll20_oriented_t_minus60_to_plus60'][60:])
    if len(x) and np.isfinite(x[0]) and abs(x[0])>1e-12:
        z=x/x[0]
        for t in (0,.1,.25,.5):
            q=np.where(z<=t)[0]
            if len(q): return int(q[0])
    return 60

def add(nodes,sec,px,why):
    sec=max(0,int(round(sec)))
    if nodes and sec<=nodes[-1]['seconds_from_t0']: sec=nodes[-1]['seconds_from_t0']+1
    nodes.append({'seconds_from_t0':sec,'forecast_price':round(float(px),3),'market_condition':why})

def predict(r):
    fam=r['family']; pol=int(r['dipole_polarity']); anchor=float(r['causal_price_anchor']['value']); sc,parts=support(r); state=r['frozen_post_state_assignment'].get('label'); nodes=[]
    add(nodes,0,anchor,'causal t0 price anchor; future price withheld')
    if fam=='A' and state=='A-persistent':
        d=A_DURS[state]; mx=clip(9+4*(sc+1)/2,8,13); add(nodes,20 if sc>=0 else 30,anchor+pol*clip(1.2+1.2*max(sc,0),1,3)*TICK,'persistent dipole retains early authority'); add(nodes,60,anchor+pol*clip(3+2*sc,1.5,5)*TICK,'persistent post-state remains live through observed exhaustion window'); add(nodes,d['3t'],anchor+pol*clip(5+2*sc,3.5,7)*TICK,'persistent local runway phase'); add(nodes,d['5t'],anchor+pol*clip(7+2*sc,5,9)*TICK,'same-side grind extends into broader leg'); add(nodes,d['8t'],anchor+pol*clip(mx-1,7,12)*TICK,'broad continuation matures'); add(nodes,d['13t'],anchor+pol*(mx if sc>.35 else mx-1.5)*TICK,'terminal broad-state forecast after persistence matures'); conf='high'; proj='same-side continuation from dipole polarity; persistent A carries local-to-broad runway'; reason=f'Frozen A-persistent centroid assignment; oriented legal post-window support={sc:+.2f}. Best curve keeps the dipole side in control with late deceleration.'; fals='Fails if the realized curve loses the dipole side early and does not out-run fast-collapse at 3t/5t/8t.'
    elif fam=='A':
        d=A_DURS[state]; peak=clip(3+1.5*max(sc,0),2,5); turn=clip(exhaustion_time(r),15,60); add(nodes,min(20,turn),anchor+pol*clip(2.2+1.2*max(sc,0),1.5,4)*TICK,'initial dipole-side push before authority collapse'); add(nodes,turn,anchor+pol*peak*TICK,'fast-collapse exhaustion/turn window'); retr=clip(.65-.35*sc,.35,1.15); add(nodes,60,anchor+pol*peak*(1-retr)*TICK,'post-collapse path loses most initial extension'); add(nodes,d['3t'],anchor+pol*clip(1.5+sc,-.5,2.5)*TICK,'short local runway after fast collapse'); broad=(-pol*clip((-sc)*2,0,3)*TICK) if sc<0 else pol*clip(sc*1.5,0,2)*TICK; add(nodes,d['5t'],anchor+broad,'broader leg lacks persistent A authority'); add(nodes,d['8t'],anchor+broad*.8,'late stabilization after collapsed authority'); add(nodes,d['13t'],anchor+broad*.5,'terminal state near anchor after fast-collapse regime'); conf='high'; proj='initial dipole-side move followed by early exhaustion/fade; materially shorter runway than persistent A'; reason=f'Frozen A-fast-collapse centroid assignment; oriented legal post-window support={sc:+.2f}. Best curve allows a small initial push then fades as authority collapses.'; fals='Fails if the realized curve preserves same-side authority and develops persistent-A-like 3t/5t/8t runway.'
    elif fam=='B':
        d=B_DURS; local=clip(3+2*sc,1.5,5); add(nodes,20,anchor+pol*clip(local*.45,.5,2.5)*TICK,'B local impulse begins on dipole side'); add(nodes,60,anchor+pol*local*TICK,'B family strongest at local/small scale'); add(nodes,d['3t'],anchor+pol*clip(local+.8,2,5.5)*TICK,'local 3t authority peaks'); add(nodes,d['5t'],anchor+pol*clip(1+2.5*sc,-3,3)*TICK,'B authority degrades as scale broadens'); opp=clip(-1+2*sc,-4,2); add(nodes,d['8t'],anchor+pol*opp*TICK,'broad B direction low-confidence; local impulse spent'); add(nodes,d['13t'],anchor+pol*clip(opp*.8,-4,2)*TICK,'terminal broad state after B locality fades'); conf='low'; proj='dipole-side local impulse near 3t; directional authority degrades at broader scales rather than forcing an opposite call'; reason=f'Frozen B locality rule; oriented legal post-window support={sc:+.2f}. Best curve gives the dipole side a local impulse then fades the broad directional edge.'; fals='Fails if broad 8t/13t behavior is as directionally reliable as the local 3t move.'; state=None
    else:
        d=C_DURS; opp=clip(2-1.2*sc,.8,3.5); add(nodes,20,anchor-pol*opp*.5*TICK,'C transition allows immediate micro-leg against dipole polarity'); add(nodes,60,anchor-pol*opp*TICK,'local 2t/3t C behavior remains weakly/oppositely aligned'); add(nodes,d['3t'],anchor-pol*clip(opp*.6,.5,2.5)*TICK,'C local transition begins to exhaust'); b5=clip(4+2*sc,2,6); add(nodes,d['5t'],anchor+pol*b5*TICK,'C broader structure takes over; alignment improves'); b8=clip(6+2.5*sc,3.5,8.5); add(nodes,d['8t'],anchor+pol*b8*TICK,'broader C leg continues on dipole side'); add(nodes,d['13t'],anchor+pol*clip(b8+1.5,5,10)*TICK,'terminal broad C state; local contradiction resolved'); conf='low'; proj='possible opposite/weak local 2t/3t move transitioning toward dipole-side alignment at 5t/8t/13t'; reason=f'Frozen C scale-transition rule; oriented legal post-window support={sc:+.2f}. Best path permits a local counter-move before broader dipole-side structure takes control.'; fals='Fails if alignment does not improve from local 2t/3t into broader 5t/8t/13t structure.'; state=None
    micro='same-side' if sc>.15 else ('opposite' if sc<-.15 else 'mixed/sparse')
    return {'blind_id':r['blind_id'],'family':fam,'day':r['day'],'t0_second_utc':int(r['t0_second_utc']),'price_anchor':anchor,'post_state':state,'best_price_curve':nodes,'path_price_curve':[[n['seconds_from_t0'],n['forecast_price']] for n in nodes],'predicted_duration_s':d,'directional_scale_projection':proj,'confidence':conf,'reasoning':reason,'brain_attribution':list(BRAIN_IDS),'microstructure_read':{'classification':micro,'oriented_support_score':round(float(sc),4),'components':{k:(None if v is None else round(float(v),4)) for k,v in parts.items()}},'falsifier':fals,'outcome_accessed':False}

def main():
    schema=json.loads(SCHEMA.read_text()); man=json.loads(INPUT_MANIFEST.read_text()); brain=json.loads(BRAIN.read_text()); rows=json.loads(RECORDS.read_text())
    if schema.get('schema_id')!='FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_V2_SINGLE_BEST_CURVE_20260816' or schema['curve_contract'].get('uncertainty_bands') is not False: raise SystemExit('single-best-curve schema drift')
    if man.get('blind_n')!=1711 or man.get('future_price_or_price_bearing_window_served') is not False or man.get('blind_record_outcome_wall_scan')!='PASS': raise SystemExit('blind input invariant failure')
    play_ids={p.get('id') for p in brain.get('plays',[])}
    if any(x not in play_ids for x in BRAIN_IDS): raise SystemExit('required brain concept missing')
    preds=[predict(r) for r in rows]
    if len(preds)!=1711 or len({p['blind_id'] for p in preds})!=1711: raise SystemExit('prediction coverage failure')
    for p in preds:
        if p['outcome_accessed'] or p['best_price_curve'][0]['seconds_from_t0']!=0 or p['best_price_curve'][0]['forecast_price']!=p['price_anchor']: raise SystemExit('prediction guard failure')
        if p['path_price_curve']!=[[n['seconds_from_t0'],n['forecast_price']] for n in p['best_price_curve']]: raise SystemExit('curve projection drift')
        if any(any(k.lower().startswith(('p25','p50','p75')) for k in n) for n in p['best_price_curve']): raise SystemExit('uncertainty band leaked into single-curve output')
    OUT.mkdir(parents=True,exist_ok=True); shards={}
    for day in sorted({p['day'] for p in preds}):
        data=''.join(json.dumps(p,separators=(',',':'),sort_keys=True)+'\n' for p in preds if p['day']==day).encode(); gz=gzip.compress(data,compresslevel=9,mtime=0); path=OUT/f'frankie_ng_blind_predictions_{day}.jsonl.gz'; path.write_bytes(gz); shards[path.name]={'day':day,'records':sum(p['day']==day for p in preds),'sha256':hashlib.sha256(gz).hexdigest(),'uncompressed_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(gz)}
    freeze={'status':'FROZEN_BLIND_PREDICTIONS_PENDING_REVEAL','model_transport':'ChatGPT applying Frankie frozen experiment context and unchanged target-day-redacted brain','schema_id':schema['schema_id'],'schema_commit':'58970b54fb8b6cd9f0d6e34dc34cdfaf538fcb77','input_artifact_id':9274443976,'input_artifact_digest':'sha256:224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39','frozen_a_classifier_sha256':man['a_classifier_sha256'],'prediction_n':len(preds),'family_counts':dict(Counter(p['family'] for p in preds)),'a_post_state_counts':dict(Counter(p['post_state'] for p in preds if p['family']=='A')),'single_best_curve_only':True,'uncertainty_bands':False,'outcome_accessed_before_freeze':False,'future_price_served_to_model':False,'causal_t0_anchor_served':True,'shards':shards}
    (OUT/'FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json').write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
    print(json.dumps(freeze,indent=2,sort_keys=True))
if __name__=='__main__': main()
