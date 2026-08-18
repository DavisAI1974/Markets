#!/usr/bin/env python3
from __future__ import annotations
import argparse,bisect,gzip,json,math,re
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path

import ng_exhaustion_exact_d1_agents_20260818 as core
from ng_dipole_runway_audit import TICK


def day_from_name(p):
    m=re.search(r'(20\d{6})',Path(p).name)
    if not m:raise SystemExit(f'cannot parse day {p}')
    return m.group(1)
def sunday(s):return datetime.strptime(s,'%Y%m%d')
def load_week_prices(raw_paths,week):
    sun=sunday(week);pts=[]
    for p in raw_paths:
        d=day_from_name(p);di=(datetime.strptime(d,'%Y%m%d')-sun).days
        if di<0 or di>5:continue
        with gzip.open(p,'rt') as f:
            for line in f:
                r=json.loads(line)
                if r.get('action')!='T':continue
                px=float(r.get('price',0) or 0)
                if px<=0:continue
                ts=float(r.get('ts_event',r.get('ts',0.0)));sec=int(ts)%86400;pts.append((di*86400+sec,px))
    pts.sort();return pts
def path_stats(pts,start,end,pol):
    if not pts or end<=start:return None
    idx=[x[0] for x in pts];j=max(0,bisect.bisect_right(idx,start)-1);k=bisect.bisect_right(idx,end)
    seg=pts[j:k]
    if len(seg)<2:return None
    p0=seg[0][1];p1=seg[-1][1];oriented=[pol*(p-p0)/TICK for _,p in seg];changes=[seg[i][1]-seg[i-1][1] for i in range(1,len(seg))]
    total=sum(abs(x) for x in changes);signed=pol*(p1-p0)/TICK;mfe=max(oriented);mae=min(oriented)
    max_exc=max(abs(mfe),abs(mae));two_side_min=min(max(mfe,0.0),max(-mae,0.0));two_side_max=max(max(mfe,0.0),max(-mae,0.0))
    return {
      'trade_points':len(seg),'duration_seconds':end-start,'signed_endpoint_ticks':signed,
      'mfe_ticks':mfe,'mae_ticks':mae,'range_ticks':mfe-mae,
      'path_efficiency':abs(p1-p0)/total if total>0 else 0.0,
      'endpoint_to_excursion_efficiency':abs(signed)/max_exc if max_exc>0 else 0.0,
      'two_sidedness':two_side_min/two_side_max if two_side_max>0 else 0.0,
      'aligned_change_fraction':sum(pol*x>0 for x in changes)/len(changes) if changes else None,
      'entry_price':p0,'exit_price':p1
    }
def summarize(rows,key):return core.summary([r[key] for r in rows if core.finite(r.get(key))])
def _logit(x):
    x=min(max(float(x),1e-6),1-1e-6);return math.log(x/(1-x))
def fit_shape_model(rows):
    import numpy as np
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    tr=[r for r in rows if r['block']=='train' and all(core.finite(r.get(k)) for k in ('path_efficiency','endpoint_to_excursion_efficiency','two_sidedness'))]
    if len(tr)<20:raise SystemExit(f'insufficient train raw paths for shape model: {len(tr)}')
    raw=np.asarray([[_logit(r['path_efficiency']),_logit(r['endpoint_to_excursion_efficiency']),_logit(r['two_sidedness'])] for r in tr],float)
    sc=StandardScaler().fit(raw);X=sc.transform(raw);g=GaussianMixture(n_components=2,random_state=20260818,n_init=30).fit(X)
    zcent=g.means_;cent=sc.inverse_transform(zcent)
    def invlogit(v):return 1/(1+math.exp(-float(v)))
    orig=[[invlogit(x) for x in row] for row in cent]
    # Chop = lower directional/path efficiency and higher two-sidedness.
    score=[row[0]+row[1]-row[2] for row in orig];chop=int(min(range(2),key=lambda i:score[i]));directional=1-chop
    return {'scaler':sc,'gmm':g,'chop_component':chop,'directional_component':directional,'centers_original':orig,'train_n':len(tr)}
def assign_shape(model,r):
    import numpy as np
    x=np.asarray([[_logit(r['path_efficiency']),_logit(r['endpoint_to_excursion_efficiency']),_logit(r['two_sidedness'])]],float)
    c=int(model['gmm'].predict(model['scaler'].transform(x))[0])
    return 'CHOP_ROTATION' if c==model['chop_component'] else 'DIRECTIONAL'
def group_summary(rows):
    return {
      'n':len(rows),'signed_endpoint_ticks':summarize(rows,'signed_endpoint_ticks'),'mfe_ticks':summarize(rows,'mfe_ticks'),
      'mae_ticks':summarize(rows,'mae_ticks'),'range_ticks':summarize(rows,'range_ticks'),'path_efficiency':summarize(rows,'path_efficiency'),
      'endpoint_to_excursion_efficiency':summarize(rows,'endpoint_to_excursion_efficiency'),'two_sidedness':summarize(rows,'two_sidedness'),
      'aligned_change_fraction':summarize(rows,'aligned_change_fraction'),'duration_seconds':summarize(rows,'duration_seconds'),
      'pair_counts':dict(Counter(r['pair'] for r in rows))
    }
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--held',required=True);ap.add_argument('--base-lineage',required=True);ap.add_argument('--held-lineage',required=True);ap.add_argument('--summary',required=True);ap.add_argument('--raw-dir',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    weeks=json.load(open(a.summary))['weeks'];events=core.load_events(a.base,a.held);lineage=core.load_lineage(a.base_lineage,a.held_lineage);d1,model=core.d1_records(events,lineage,weeks);longfam=model['labels'][-1]
    longweeks=sorted(set(r['week'] for r in d1 if r['block']!='held' and r['duration_family']==longfam));raw=list(Path(a.raw_dir).glob('NG_*.jsonl.gz'));out=[]
    for w in longweeks:
        wp=[p for p in raw if day_from_name(p)>=w and day_from_name(p)<=(sunday(w)+timedelta(days=5)).strftime('%Y%m%d')];pts=load_week_prices(wp,w)
        for r in [z for z in d1 if z['week']==w]:
            o=events[w][r['origin_seq']];d=events[w][r['origin_seq']+1]
            if o.get('confirm') is None:continue
            start=int(o['confirm'])+60;end=int(d['t0']);z=path_stats(pts,start,end,o['pol'])
            if z is None:continue
            z.update({'week':w,'block':r['block'],'pair':r['pair'],'duration_family':r['duration_family'],'elapsed_origin_to_desc':r['elapsed'],'origin_event_id':r['origin_event_id'],'desc_event_id':r['desc_event_id'],'origin_wall_to_desc_t0':r['origin_wall_to_desc_t0']});out.append(z)
    shape=fit_shape_model(out)
    for r in out:r['path_shape_group']=assign_shape(shape,r)
    family_cells={}
    for fam in model['labels']:
        R=[r for r in out if r['duration_family']==fam];family_cells[fam]=group_summary(R)
    shape_cells={}
    for g in ('DIRECTIONAL','CHOP_ROTATION'):
        R=[r for r in out if r['path_shape_group']==g];shape_cells[g]={'all':group_summary(R),'blocks':{b:group_summary([r for r in R if r['block']==b]) for b in ('train','era13','era45','conf')},'duration_families':dict(Counter(r['duration_family'] for r in R))}
    res={
      'status':'EXACT_D1_RAWPATH_AGENT_COMPLETE','long_family':longfam,'long_case_weeks':longweeks,'train_family_centers_seconds':model['centers'],
      'path_shape_model':{'method':'train-only 2-component GaussianMixture on standardized logit(path_efficiency, endpoint_to_excursion_efficiency, two_sidedness)','train_n':shape['train_n'],'centers_original_ordered_by_component':shape['centers_original'],'chop_component':shape['chop_component'],'directional_component':shape['directional_component'],'rule':'lower efficiency + higher two-sidedness component labeled CHOP_ROTATION; model frozen before later-block assignment'},
      'family_summaries':family_cells,'path_shape_groups':shape_cells,'records':out,
      'guard':'CHOP_ROTATION is preserved as its own potentially profitable population; raw path uses frozen event indices only, no redetection, no retrospective intraleg strategy optimization, and no claim that realized path-shape identity was known at origin',
      'promotion_performed':False,'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}
    }
    Path(a.out).write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
