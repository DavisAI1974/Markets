#!/usr/bin/env python3
from __future__ import annotations

import argparse, gzip, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

STATE_CODE={
 'persistent_exhaustion':'P','collapsed_opposite_flow_reversal':'O',
 'collapsed_same_flow_reload':'S','collapsed_sparse_indeterminate':'X'
}
BLOCKS=('train','era13','era45','conf','held'); OOT=('era13','era45','conf')


def finite(x):
    try:return math.isfinite(float(x))
    except Exception:return False

def mean(xs):return sum(xs)/len(xs) if xs else None
def median(xs):return statistics.median(xs) if xs else None
def quantile(xs,q):
    a=sorted(float(x) for x in xs if finite(x))
    if not a:return None
    z=(len(a)-1)*q;i=int(math.floor(z));j=int(math.ceil(z))
    return a[i] if i==j else a[i]*(j-z)+a[j]*(z-i)
def summary(xs):
    a=[float(x) for x in xs if finite(x)]
    return {'n':len(a),'mean':mean(a),'median':median(a),'p25':quantile(a,.25),'p75':quantile(a,.75),'p90':quantile(a,.90),'p95':quantile(a,.95),'p99':quantile(a,.99),'max':max(a) if a else None}
def binom_upper(k,n):
    if n<=0:return None
    return sum(math.comb(n,j) for j in range(k,n+1))/(2**n)
def bh(items):
    vals=sorted([(k,float(v)) for k,v in items if v is not None],key=lambda z:z[1]);m=len(vals);out={};nxt=1.0
    for rank in range(m,0,-1):
        k,p=vals[rank-1];q=min(nxt,p*m/rank,1.0);out[k]=q;nxt=q
    return out

def block_for(w,weeks):
    if w=='20260329':return 'held'
    i=weeks.index(w)
    return 'train' if i<18 else 'era13' if i<36 else 'era45' if i<48 else 'conf'
def hval(r,h,m='signed_displacement_ticks'):
    z=((r.get('outcome') or {}).get('post_endpoint_price') or {}).get('horizons',{}).get(str(h),{})
    v=z.get(m);return None if z.get('censored',False) or not finite(v) else float(v)
def load_events(*paths):
    by=defaultdict(dict)
    for path in paths:
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line);w=r['week_sunday'];i=int(r['sequence_index']);ep=r.get('dynamic_endpoint') or {};ft=r.get('feature') or {}
                by[w][i]={
                  'week':w,'seq':i,'event_id':r.get('event_id'),'t0':int(r['t0_idx']),
                  'state':r.get('seed_state'),'code':STATE_CODE.get(r.get('seed_state'),'?'),'pol':int(r['polarity']),
                  'family':r.get('family'),'a_state':r.get('a_frozen_post_state'),
                  'confirm':ep.get('causal_confirmation_idx'),'onset':ep.get('structural_onset_idx'),
                  'feature':ft,
                  'h':{str(h):{m:hval(r,h,m) for m in ('signed_displacement_ticks','mfe_ticks','mae_ticks')} for h in (5,10,20,30,60,120,300)}
                }
    return {w:dict(sorted(v.items())) for w,v in by.items()}
def load_lineage(*paths):
    d={}
    for path in paths:
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line);d[(r['week_sunday'],int(r['origin_sequence_index']))]={'depth':int(r.get('all_model_consecutive_positive_depth',0)),'elapsed':r.get('consensus_elapsed_seconds')}
    return d

def fit_family_model(d1):
    import numpy as np
    from sklearn.mixture import GaussianMixture
    train=[r['elapsed'] for r in d1 if r['block']=='train' and r['elapsed']>0]
    X=np.log(np.asarray(train,float)).reshape(-1,1);models=[]
    for k in range(1,min(5,len(train))+1):
        g=GaussianMixture(n_components=k,random_state=20260818,n_init=20).fit(X);models.append((g.bic(X),k,g))
    bic,k,g=min(models,key=lambda z:z[0]);order=np.argsort(g.means_.ravel());raw_to_ord={int(raw):i for i,raw in enumerate(order)}
    centers=np.exp(g.means_.ravel()[order]).tolist()
    labels=['only'] if k==1 else ['short','long'] if k==2 else ['short','middle','long'] if k==3 else ['very_short','short','middle','long'] if k==4 else [f'f{i+1}' for i in range(k-1)]+['long']
    return {'bic':bic,'k':k,'g':g,'raw_to_ord':raw_to_ord,'centers':centers,'labels':labels,'bic_grid':[{'k':kk,'bic':bb} for bb,kk,_ in sorted(models,key=lambda z:z[1])]}
def assign_family(model,x):
    import numpy as np
    if not finite(x) or x<=0:return None
    raw=int(model['g'].predict(np.log(np.asarray([[float(x)]])))[0]);o=model['raw_to_ord'][raw]
    return model['labels'][o]

def d1_records(events,lineage,weeks):
    out=[]
    for w,rows in events.items():
        b=block_for(w,weeks)
        for i,o in rows.items():
            lr=lineage.get((w,i))
            if not lr or lr['depth']!=1 or not finite(lr.get('elapsed')) or i+1 not in rows:continue
            d=rows[i+1];elapsed=int(lr['elapsed']);older=rows.get(i-1);older_code=None
            if older and older.get('confirm') is not None and int(older['confirm'])+60<=o['t0']:older_code=older['code']
            child=lineage.get((w,i+1),{'depth':0,'elapsed':None});wall=None if o.get('confirm') is None else int(o['confirm'])+60
            r5=d['h']['5']['signed_displacement_ticks'];r60=d['h']['60']['signed_displacement_ticks'];ret=None if r5 is None or r60 is None else r60-r5
            out.append({
              'week':w,'block':b,'origin_seq':i,'origin_event_id':o['event_id'],'desc_event_id':d['event_id'],'elapsed':elapsed,
              'pair':o['code']+d['code']+'|'+('S' if o['pol']==d['pol'] else 'F'),'origin_code':o['code'],'desc_code':d['code'],
              'origin_pol':o['pol'],'desc_pol':d['pol'],'older_code':older_code,'origin_family':o.get('family'),'origin_a_state':o.get('a_state'),
              'origin_feature':o.get('feature') or {},'desc_ret60_from5':ret,'desc_h':d['h'],'origin_h':o['h'],
              'origin_wall_to_desc_t0':None if wall is None else d['t0']-wall,'child_depth':int(child.get('depth') or 0),'child_elapsed':child.get('elapsed'),
            })
    m=fit_family_model(out)
    for r in out:r['duration_family']=assign_family(m,r['elapsed'])
    return out,m

def cells(recs,value_fn,orientation=1):
    out={}
    for b in BLOCKS:
        R=[r for r in recs if r['block']==b];vals=[orientation*value_fn(r) for r in R if finite(value_fn(r))]
        out[b]={'n':len(vals),'mean':mean(vals),'median':median(vals),'positive_rate':sum(v>0 for v in vals)/len(vals) if vals else None,'weeks':len(set(r['week'] for r in R if finite(value_fn(r))))}
    return out

def lane_lifespan(d1,model):
    fam={}
    for b in BLOCKS:
        R=[r for r in d1 if r['block']==b];fam[b]={'elapsed':summary([r['elapsed'] for r in R]),'families':dict(Counter(r['duration_family'] for r in R))}
    return {'train_model':{'selected_components':model['k'],'centers_seconds':model['centers'],'labels':model['labels'],'bic':model['bic'],'bic_grid':model['bic_grid']},'blocks':fam}
def lane_grammar(d1):
    out=[]
    keys=sorted(set((r['pair'],r['duration_family']) for r in d1))
    for p,f in keys:
        B={}
        for b in BLOCKS:
            R=[r for r in d1 if r['pair']==p and r['duration_family']==f and r['block']==b]
            B[b]={'n':len(R),'elapsed':summary([r['elapsed'] for r in R])}
        if sum(B[b]['n'] for b in OOT)>=5:out.append({'pair':p,'duration_family':f,'blocks':B})
    out.sort(key=lambda z:sum(z['blocks'][b]['n'] for b in OOT),reverse=True);return out
def lane_decompose(d1):
    out=[]
    for p in sorted(set(r['pair'] for r in d1)):
        R=[r for r in d1 if r['pair']==p and finite(r['desc_ret60_from5'])];tr=[r['desc_ret60_from5'] for r in R if r['block']=='train']
        if len(tr)<20 or abs(mean(tr) or 0)<1e-12:continue
        ori=1 if mean(tr)>0 else -1;splits={}
        for field in ('duration_family','older_code','origin_family','origin_a_state'):
            D={}
            for val in sorted(set(str(r.get(field)) for r in R)):
                Q=[r for r in R if str(r.get(field))==val];v=[ori*r['desc_ret60_from5'] for r in Q]
                D[val]={'n':len(v),'mean_oriented':mean(v),'positive_rate':sum(x>0 for x in v)/len(v) if v else None,'blocks':cells(Q,lambda x:x['desc_ret60_from5'],ori)}
            splits[field]=D
        out.append({'pair':p,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','splits':splits,'policy':'FLAG_AND_DECOMPOSE_NOT_AUTO_KILL'})
    return out
def lane_outcome(d1):
    out=[]
    for p,f in sorted(set((r['pair'],r['duration_family']) for r in d1)):
        R=[r for r in d1 if r['pair']==p and r['duration_family']==f]
        if sum(r['block']=='train' for r in R)<15:continue
        tr=[r['desc_ret60_from5'] for r in R if r['block']=='train' and finite(r['desc_ret60_from5'])]
        if not tr or abs(mean(tr) or 0)<1e-12:continue
        ori=1 if mean(tr)>0 else -1;B={}
        for b in BLOCKS:
            Q=[r for r in R if r['block']==b];B[b]={'n':len(Q),'reference_return':cells(Q,lambda x:x['desc_ret60_from5'],ori)[b],
              'origin_h60':summary([ori*(r['origin_h']['60']['signed_displacement_ticks'] or 0) for r in Q if r['origin_h']['60']['signed_displacement_ticks'] is not None]),
              'desc_endpoint_mfe60':summary([ori*r['desc_h']['60']['mfe_ticks'] for r in Q if r['desc_h']['60']['mfe_ticks'] is not None]),
              'desc_endpoint_mae60':summary([ori*r['desc_h']['60']['mae_ticks'] for r in Q if r['desc_h']['60']['mae_ticks'] is not None])}
        out.append({'pair':p,'duration_family':f,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','blocks':B})
    return out
def lane_causal(d1):
    out=[]
    for f in sorted(set(r['duration_family'] for r in d1)):
        R=[r for r in d1 if r['duration_family']==f];B={}
        for b in BLOCKS:
            Q=[r for r in R if r['block']==b];lead=[r['origin_wall_to_desc_t0'] for r in Q if finite(r['origin_wall_to_desc_t0'])]
            B[b]={'n':len(Q),'wall_to_desc_t0_seconds':summary(lead),'positive_remaining_rate':sum(x>0 for x in lead)/len(lead) if lead else None}
        out.append({'duration_family':f,'blocks':B,'guard':'family is realized at descendant; positive remaining time alone does not make family identity causal at the origin'})
    return out
def lane_reorigin(d1):
    out=[]
    for p,f in sorted(set((r['pair'],r['duration_family']) for r in d1)):
        R=[r for r in d1 if r['pair']==p and r['duration_family']==f]
        if sum(r['block'] in OOT for r in R)<5:continue
        B={}
        for b in BLOCKS:
            Q=[r for r in R if r['block']==b];c=Counter(r['child_depth'] for r in Q)
            B[b]={'n':len(Q),'child_depth_hist':dict(c),'reorigin_positive_depth_rate':sum(r['child_depth']>0 for r in Q)/len(Q) if Q else None,'child_elapsed':summary([r['child_elapsed'] for r in Q if finite(r['child_elapsed'])])}
        out.append({'pair':p,'duration_family':f,'blocks':B})
    return out

def candidate_key(r,kind):
    if kind=='pair':return r['pair']
    if kind=='pair_family':return r['pair']+'|DUR='+str(r['duration_family'])
    if kind=='pair_older':return r['pair']+'|OLDER='+str(r['older_code'])
    if kind=='pair_family_older':return r['pair']+'|DUR='+str(r['duration_family'])+'|OLDER='+str(r['older_code'])
    if kind=='pair_originfamily':return r['pair']+'|FAM='+str(r['origin_family'])
    raise KeyError(kind)
def profit_stats(R,ori,cost):
    vals=[ori*r['desc_ret60_from5']-cost for r in R if finite(r['desc_ret60_from5'])];weeks=defaultdict(list)
    for r in R:
        if finite(r['desc_ret60_from5']):weeks[r['week']].append(ori*r['desc_ret60_from5']-cost)
    wm={w:mean(v) for w,v in weeks.items()};loo=[]
    if len(vals)>1:
        for w in wm:
            z=[ori*r['desc_ret60_from5']-cost for r in R if r['week']!=w and finite(r['desc_ret60_from5'])]
            if z:loo.append(mean(z))
    return {'n':len(vals),'mean':mean(vals),'median':median(vals),'positive_rate':sum(v>0 for v in vals)/len(vals) if vals else None,'weeks':len(wm),'positive_week_fraction':sum(v>0 for v in wm.values())/len(wm) if wm else None,'leave_one_week_out_min_mean':min(loo) if loo else None,'week_means':wm}
def lane_profit(d1):
    kinds=('pair','pair_family','pair_older','pair_family_older','pair_originfamily');cands=[]
    for kind in kinds:
        D=defaultdict(list)
        for r in d1:D[candidate_key(r,kind)].append(r)
        for key,R in D.items():
            tr=[r for r in R if r['block']=='train' and finite(r['desc_ret60_from5'])]
            if len(tr)<30:continue
            tm=mean([r['desc_ret60_from5'] for r in tr])
            if tm is None or abs(tm)<1e-12:continue
            ori=1 if tm>0 else -1;B={}
            for b in BLOCKS:
                Q=[r for r in R if r['block']==b];B[b]={'gross':profit_stats(Q,ori,0.0),'net_0_5':profit_stats(Q,ori,.5),'net_1':profit_stats(Q,ori,1.0),'net_2':profit_stats(Q,ori,2.0)}
            oot_weeks=[]
            for b in OOT:
                oot_weeks.extend(B[b]['gross']['week_means'].values())
            p=binom_upper(sum(v>0 for v in oot_weeks),len(oot_weeks)) if oot_weeks else None
            worst05=min([B[b]['net_0_5']['mean'] for b in OOT if B[b]['net_0_5']['mean'] is not None] or [None])
            cands.append({'kind':kind,'candidate':key,'orientation':'WITH_CURRENT' if ori==1 else 'AGAINST_CURRENT','train_n':len(tr),'blocks':B,'oot_week_sign_p':p,'worst_oot_net_0_5':worst05})
    q=bh([(i,c['oot_week_sign_p']) for i,c in enumerate(cands)])
    for i,c in enumerate(cands):
        c['oot_week_sign_q_bh']=q.get(i);c['stable_net_0_5_all_oot']=c['worst_oot_net_0_5'] is not None and c['worst_oot_net_0_5']>0
    cands.sort(key=lambda c:(c['stable_net_0_5_all_oot'],c['worst_oot_net_0_5'] if c['worst_oot_net_0_5'] is not None else -1e9,c['blocks']['conf']['net_0_5']['mean'] if c['blocks']['conf']['net_0_5']['mean'] is not None else -1e9),reverse=True)
    return {'candidate_count':len(cands),'stable_net_0_5_count':sum(c['stable_net_0_5_all_oot'] for c in cands),'candidates':cands}
def lane_predictor(events,lineage,weeks,d1,model):
    import numpy as np
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score,brier_score_loss
    long_label=model['labels'][-1]
    long_keys={(r['week'],r['origin_seq']) for r in d1 if r['duration_family']==long_label}
    rows=[]
    for w,E in events.items():
        b=block_for(w,weeks)
        for i,e in E.items():
            ft=e.get('feature') or {}
            rows.append({'week':w,'block':b,'y':1 if (w,i) in long_keys else 0,'state':e['code'],'family':str(e.get('family')),'a_state':str(e.get('a_state')),
                         'peak_abs':ft.get('peak_abs'),'pre_prominence':ft.get('pre_prominence'),'exh_t50_s':ft.get('exh_t50_s'),'exh_t25_s':ft.get('exh_t25_s'),'exh_t10_s':ft.get('exh_t10_s'),'zero':ft.get('exh_zero_onset_within60_s'),'roll60':ft.get('roll20_at60'),'late_flow':ft.get('late_flow_pressure_41_60'),'book_late':ft.get('book_aligned_late_mean'),'book_change':ft.get('book_aligned_change_from_t0')})
    num=['peak_abs','pre_prominence','exh_t50_s','exh_t25_s','exh_t10_s','zero','roll60','late_flow','book_late','book_change'];cat=['state','family','a_state']
    tr=[r for r in rows if r['block']=='train'];Xtr=[[r.get(k) for k in num+cat] for r in tr];ytr=[r['y'] for r in tr]
    if len(set(ytr))<2:return {'status':'NO_TRAIN_CLASS_VARIATION'}
    pre=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median')),('sc',StandardScaler())]),list(range(len(num)))),('cat',Pipeline([('imp',SimpleImputer(strategy='most_frequent')),('oh',OneHotEncoder(handle_unknown='ignore'))]),list(range(len(num),len(num)+len(cat))))])
    pipe=Pipeline([('pre',pre),('clf',LogisticRegression(max_iter=2000,class_weight='balanced',C=1.0))]);pipe.fit(Xtr,ytr)
    out={'target':'exact_D1_train_frozen_long_family_vs_all_origins','long_family':long_label,'train_n':len(tr),'train_positive':sum(ytr),'blocks':{}}
    for b in OOT+('held',):
        R=[r for r in rows if r['block']==b];X=[[r.get(k) for k in num+cat] for r in R];y=np.asarray([r['y'] for r in R],int)
        if not R:continue
        p=pipe.predict_proba(X)[:,1];order=np.argsort(p)[::-1];topn=max(1,int(math.ceil(.10*len(R))));top=y[order[:topn]]
        out['blocks'][b]={'n':len(R),'positives':int(y.sum()),'base_rate':float(y.mean()),'auc':float(roc_auc_score(y,p)) if len(set(y.tolist()))>1 else None,'brier':float(brier_score_loss(y,p)),'top_decile_n':topn,'top_decile_positive_rate':float(top.mean()),'top_decile_lift':float(top.mean()/y.mean()) if y.mean()>0 else None}
    out['guard']='predictor uses only origin canonical characteristics; positive validation is required before any origin-to-descendant long-leg execution research'
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',required=True,choices=['lifespan','grammar','decompose','outcome','causal','reorigin','profit','predictor']);ap.add_argument('--base',required=True);ap.add_argument('--held',required=True);ap.add_argument('--base-lineage',required=True);ap.add_argument('--held-lineage',required=True);ap.add_argument('--summary',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    weeks=json.load(open(a.summary))['weeks'];events=load_events(a.base,a.held);lineage=load_lineage(a.base_lineage,a.held_lineage);d1,model=d1_records(events,lineage,weeks)
    f={'lifespan':lambda:lane_lifespan(d1,model),'grammar':lambda:lane_grammar(d1),'decompose':lambda:lane_decompose(d1),'outcome':lambda:lane_outcome(d1),'causal':lambda:lane_causal(d1),'reorigin':lambda:lane_reorigin(d1),'profit':lambda:lane_profit(d1),'predictor':lambda:lane_predictor(events,lineage,weeks,d1,model)}[a.mode]
    result={'status':'EXACT_D1_AGENT_COMPLETE','mode':a.mode,'exact_d1_n':len(d1),'result':f(),'promotion_performed':False,'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}}
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
