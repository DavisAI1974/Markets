"""P&L-blind whole-curve classification of run-duration families.

Direct test of the visual S74/S75 hypothesis: before onset, can the entire signed
dipole mean-flow arc distinguish a short directional run from a long one?

Chronological split. Duration cutoffs learned ONLY from training durations.
No winner/loser or fee/P&L variables are used.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from leg_imbalance import extract

COINS=("sol","btc","eth","xrp")
EPS=1e-12


def rankdata(a):
    a=np.asarray(a,float); o=np.argsort(a,kind="mergesort"); r=np.empty(len(a),float); i=0
    while i<len(a):
        j=i+1
        while j<len(a) and a[o[j]]==a[o[i]]: j+=1
        r[o[i:j]]=(i+j-1)/2; i=j
    return r

def auc(y,s):
    y=np.asarray(y,int); s=np.asarray(s,float); p=y==1; n=~p
    if p.sum()==0 or n.sum()==0:return float("nan")
    r=rankdata(s); return float((r[p].sum()-p.sum()*(p.sum()-1)/2)/(p.sum()*n.sum()))

def norm_shape(A):
    B=A-A[:,[0]]; rng=np.ptp(B,axis=1); rng[rng<EPS]=1.0; return B/rng[:,None]

def point_z(train,test):
    mu=train.mean(0); sd=train.std(0); sd[sd<EPS]=1.0; return (train-mu)/sd,(test-mu)/sd

def proto_score(trainA,trainy,testA):
    s=trainA[trainy==0].mean(0); l=trainA[trainy==1].mean(0)
    ds=np.mean((testA-s)**2,axis=1); dl=np.mean((testA-l)**2,axis=1)
    return ds-dl

def pca_logit(trainA,trainy,testA):
    ncomp=min(8,trainA.shape[0]-2,trainA.shape[1])
    p=PCA(n_components=ncomp,random_state=0).fit(trainA)
    ztr=p.transform(trainA); zte=p.transform(testA)
    sc=StandardScaler().fit(ztr); ztr=sc.transform(ztr); zte=sc.transform(zte)
    m=LogisticRegression(C=1.0,max_iter=2000).fit(ztr,trainy)
    return m.predict_proba(zte)[:,1],float(np.sum(p.explained_variance_ratio_))

def scenario(raw,y,preclock,tr,te,lo_q,hi_q):
    lo=float(np.quantile(y[tr],lo_q)); hi=float(np.quantile(y[tr],hi_q))
    trm=((y<=lo)|(y>=hi))&tr; tem=((y<=lo)|(y>=hi))&te
    ytr=(y[trm]>=hi).astype(int); yte=(y[tem]>=hi).astype(int)
    Rtr,Rte=point_z(raw[trm],raw[tem])
    Sh=norm_shape(raw); Str,Ste=point_z(Sh[trm],Sh[tem])
    pr=proto_score(Rtr,ytr,Rte); ps=proto_score(Str,ytr,Ste)
    pl,ev=pca_logit(Rtr,ytr,Rte)
    peak=raw[tem,-1]
    clock=preclock[tem]
    return {
      "train_low_cut_s":lo,"train_high_cut_s":hi,"train_n":int(trm.sum()),"test_n":int(tem.sum()),"test_long_rate":float(yte.mean()),
      "raw_whole_curve_prototype_auc":auc(yte,pr),
      "pure_shape_prototype_auc":auc(yte,ps),
      "raw_curve_pca8_logit_auc":auc(yte,pl),"pca8_train_variance_explained":ev,
      "onset_peak_alone_auc":auc(yte,peak),
      "preonset_clock_alone_auc":auc(yte,clock),
      "raw_curve_prototype_accuracy":float(np.mean((pr>0)==yte)),
      "pure_shape_prototype_accuracy":float(np.mean((ps>0)==yte)),
      "test_short_duration_median_s":float(np.median(y[tem][yte==0])) if np.any(yte==0) else None,
      "test_long_duration_median_s":float(np.median(y[tem][yte==1])) if np.any(yte==1) else None,
    }

def coin(c):
    rows,h=extract(c); y=np.array([r['dur'] for r in rows],float); raw=np.stack([np.asarray(r['t_pre_arc'],float) for r in rows]); clock=np.array([r['pre_ext'] for r in rows],float)
    n=len(y); cut=max(50,int(.70*n)); tr=np.arange(n)<cut; te=~tr
    return {"n_runs":n,"hours":float(h),"train_n":int(tr.sum()),"test_n":int(te.sum()),
      "median_split_all_runs":scenario(raw,y,clock,tr,te,.50,.50),
      "outer_40pct_drop_middle60":scenario(raw,y,clock,tr,te,.20,.80),
      "outer_50pct_drop_middle50":scenario(raw,y,clock,tr,te,.25,.75),
    }
def main():
    out={"analysis":"whole pre-onset dipole curve classifies duration family","pnl_used":False,"winner_loser_used":False,"coins":{}}
    for c in COINS:
        out['coins'][c]=coin(c); print(c,json.dumps(out['coins'][c],sort_keys=True),flush=True)
    p=Path('whole_curve_extremes_audit_results.json');p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print('RESULT_FILE='+str(p))
if __name__=='__main__':main()
