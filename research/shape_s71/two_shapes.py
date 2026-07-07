"""S71 HEADLINE: do SHORT-LOSERS and LONG-WINNERS fall into two DISTINCT arc shapes? (Greg's guarantee)
Partition btc_kraken (+majors) legs by {duration x outcome} 2x2. Overlay mean full arcs. Quantify
between-vs-within shape distance + which AXIS drives shape. Then the leakage-free PRE-ONSET predictor
of the class. Outcomes/fills from the LIVE executor. Additive; commits nothing."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
SP="/tmp/claude-0/-home-user-Markets/9c530e49-5a24-51c2-b8c4-60c751ae23a0/scratchpad"
sys.path.insert(0, SP)
from arc_gate import (load_raw, rolling_imb, preonset_features, false_start, auc,
                      build_channels, median_spread_bps, run_kraken_cell, KRAKEN, FEATNAMES)
CPS=10; PRE_SEC, POST_SEC, SMOOTH_SEC = 45, 60, 20
PRE, POST = PRE_SEC*CPS, POST_SEC*CPS
OUT=SP

def collect(coin):
    path=f"/tmp/kbook/{coin}_book.jsonl"; cfg=[c for c in KRAKEN if c.coin==coin][0]
    raw=load_raw(path); ch,g=build_channels(path,cfg.K,20,raw=raw)
    mid=np.asarray(g["mid"],float); bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    hs=median_spread_bps(path,raw=raw)/2.0; N=len(mid); hours=N*0.1/3600.0
    res,_=run_kraken_cell(cfg,mid,buy,sell,bb,ba,hs); imb=rolling_imb(buy,sell,SMOOTH_SEC)
    arcs,dur,net,gross,X=[],[],[],[],[]
    for l in res.legs:
        o=int(l.open_idx); c=int(l.close_idx); lo=o-PRE; hi=o+POST
        if lo<0 or hi>=N or c<=o: continue
        f=imb[lo:hi+1]*int(l.side)
        arcs.append(f); dur.append((c-o)*0.1); net.append(float(l.net_bps)); gross.append(float(l.gross_bps))
        X.append(preonset_features(f[:PRE+1])+[false_start(f[:PRE+1])[4]])
    return dict(coin=coin, arcs=np.array(arcs), dur=np.array(dur), net=np.array(net),
                gross=np.array(gross), X=np.array(X), hours=hours)

def desc_feats(f):
    """descriptive full-arc shape features (onset peak, sustain, rise/fall symmetry)."""
    seg=f[PRE-50:PRE+150]                      # -5..+15s around onset
    pk_rel=int(np.argmax(seg)); pk=seg[pk_rel]; pk_i=PRE-50+pk_rel
    half=0.5*pk if pk>0 else -1
    # sustain: seconds post-peak until flow first < half*peak
    post=f[pk_i:]; below=np.where(post<half)[0]
    sustain=(below[0]*0.1) if (half>0 and len(below)) else (len(post)*0.1)
    # rise time: seconds from last pre-peak crossing of half up to peak
    pre=f[:pk_i+1]; bl=np.where(pre<half)[0]
    rise=((pk_i-bl[-1])*0.1) if (half>0 and len(bl)) else pk_i*0.1
    sym=rise/(sustain+1e-9)
    return pk, sustain, rise, sym

def analyze(D, make_png=False):
    coin=D["coin"]; arcs=D["arcs"]; dur=D["dur"]; net=D["net"]; gross=D["gross"]; X=D["X"]; n=len(net)
    dmed=np.median(dur)
    short=dur<=dmed; longL=dur>dmed
    win=net>0; lose=net<=0
    parts={"short-loser":short&lose,"long-winner":longL&win,"short-winner":short&win,"long-loser":longL&lose}
    print(f"\n===== {coin}_kraken =====  legs={n}  median dur={dmed:.1f}s  base win%={win.mean():.3f}", flush=True)
    print(f"  corr(duration, net_bps) = {np.corrcoef(dur,net)[0,1]:+.3f}   "
          f"win% among long={win[longL].mean():.3f}  among short={win[short].mean():.3f}", flush=True)
    means={}
    for k,m in parts.items():
        if m.sum()<8: print(f"  {k:13s} n={m.sum():4d}  (too few)"); means[k]=None; continue
        mean=arcs[m].mean(0); means[k]=mean
        pk,sus,rise,sym=np.mean([desc_feats(arcs[i]) for i in np.where(m)[0]],axis=0)
        print(f"  {k:13s} n={m.sum():4d}  onset-peak={pk:+.3f}  sustain={sus:5.1f}s  rise={rise:4.1f}s  "
              f"rise/sustain={sym:.2f}  mean_net={net[m].mean():+.2f}", flush=True)
    # between vs within shape distance (1 - corr of onset-aligned mean arcs; within = split-half)
    def d2(a,b):
        a=a-a.mean(); b=b-b.mean(); return 1-float((a@b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))
    keys=[k for k in parts if means[k] is not None]
    print("  shape-distance (1-corr) between partition-mean full arcs:", flush=True)
    for i in range(len(keys)):
        for j in range(i+1,len(keys)):
            print(f"    {keys[i]:13s} <-> {keys[j]:13s} = {d2(means[keys[i]],means[keys[j]]):.3f}", flush=True)
    # within-partition scatter (split-half distance), rng seed
    rng=np.random.default_rng(0)
    for k in keys:
        idx=np.where(parts[k])[0]; rng.shuffle(idx); h=len(idx)//2
        wd=d2(arcs[idx[:h]].mean(0),arcs[idx[h:]].mean(0))
        print(f"    within {k:13s} (split-half) = {wd:.3f}", flush=True)
    # which AXIS drives shape: 2-way decomposition of onset-peak & sustain by duration vs outcome
    def axis_eff(feat):
        # feat per leg; effect of duration axis vs outcome axis (mean abs group-diff)
        dup=feat[longL].mean()-feat[short].mean(); out=feat[win].mean()-feat[lose].mean()
        return dup,out
    peaks=np.array([desc_feats(a)[0] for a in arcs]); suss=np.array([desc_feats(a)[1] for a in arcs])
    for nm,ft in [("onset-peak",peaks),("sustain",suss)]:
        du,ou=axis_eff(ft); print(f"  AXIS effect on {nm}: duration={du:+.3f}  outcome={ou:+.3f}", flush=True)

    # ---- PRE-ONSET predictive: short-loser vs long-winner, walk-forward OOS ----
    key_m = (short&lose)|(longL&win)
    yb = (longL&win).astype(int)               # 1=long-winner, 0=short-loser, only on the two Greg cells
    ii=np.where(key_m)[0]
    if len(ii)>40:
        ii=ii[np.argsort(ii)]                   # keep time order (legs already time-ordered)
        cut=int(len(ii)*0.6); tr=ii[:cut]; te=ii[cut:]
        ytr=yb[tr]
        if 0<ytr.sum()<len(ytr):
            sc=StandardScaler().fit(X[tr]); clf=LogisticRegression(max_iter=1000).fit(sc.transform(X[tr]),ytr)
            p=clf.predict_proba(sc.transform(X[te]))[:,1]
            a_oos=auc(yb[te],p)
            # shift null
            rng2=np.random.default_rng(1); nulls=[]
            for _ in range(200):
                yp=rng2.permutation(ytr)
                if 0<yp.sum()<len(yp):
                    cn=LogisticRegression(max_iter=200).fit(sc.transform(X[tr]),yp)
                    nulls.append(auc(yb[te],cn.predict_proba(sc.transform(X[te]))[:,1]))
            nulls=np.array(nulls); z=(a_oos-nulls.mean())/(nulls.std()+1e-9)
            print(f"  PRE-ONSET -> class {{short-loser vs long-winner}}: OOS AUC={a_oos:.3f}  "
                  f"shift-null={nulls.mean():.3f} (z={z:+.1f})  [n_tr={len(tr)} n_te={len(te)}]", flush=True)
            # ---- MONEY: gate ALL OOS legs by the two-shapes classifier (skip predicted short-losers) ----
            gcut=int(n*0.6); gte=np.arange(gcut,n)                    # global last-40% OOS
            hrs=D["hours"]*(n-gcut)/n
            p_all=clf.predict_proba(sc.transform(X[gte]))[:,1]        # P(long-winner-like)
            net_te=net[gte]; ung=net_te.sum()
            print(f"    [money] OOS ungated: net_bps={ung:.0f}  bps/hr={ung/hrs:.1f}  legs={len(gte)}", flush=True)
            for thr in (0.4,0.5,0.6):
                keep=p_all>=thr; g=net_te[keep].sum()
                print(f"    [money] gate p(long-win)>={thr}: net_bps={g:.0f}  bps/hr={g/hrs:.1f}  "
                      f"legs={keep.sum()} ({keep.mean()*100:.0f}% kept)  "
                      f"PnL retained={100*g/ung if ung!=0 else float('nan'):.0f}%", flush=True)
    return means, keys

if __name__=="__main__":
    coins=["btc","eth","sol","xrp","doge"]
    allm={}
    for c in coins:
        try:
            D=collect(c); allm[c]=analyze(D)
        except Exception as e:
            print(f"{c} FAILED: {e}", flush=True)
    # PNG: btc 2x2 partition-mean arcs overlaid (+ per-coin small multiples)
    tsec=(np.arange(PRE+POST+1)-PRE)*0.1
    fig,axs=plt.subplots(len(allm),1,figsize=(11,3.2*len(allm)),squeeze=False)
    cols={"short-loser":"C3","long-winner":"C2","short-winner":"C1","long-loser":"C4"}
    for i,(c,(means,keys)) in enumerate(allm.items()):
        ax=axs[i,0]
        for k in ["short-loser","long-winner","short-winner","long-loser"]:
            if means.get(k) is not None:
                ax.plot(tsec,means[k],color=cols[k],lw=2 if k in("short-loser","long-winner") else 1.2,
                        ls="-" if k in("short-loser","long-winner") else "--",label=k)
        ax.axvline(0,color="k",ls="--",lw=1,alpha=0.6); ax.axhline(0,color="gray",lw=0.6)
        ax.set_title(f"{c}_kraken — mean full arc by {{duration x outcome}} (aligned at onset; solid = Greg's two cells)")
        ax.set_ylabel("mean flow"); ax.legend(fontsize=7,ncol=4,loc="lower left"); ax.grid(alpha=0.25)
    axs[-1,0].set_xlabel("seconds relative to onset (t=0)")
    plt.tight_layout(); pp=os.path.join(OUT,"kraken_two_shapes.png")
    plt.savefig(pp,dpi=110); plt.close(); print(f"\nsaved {pp}\nDONE", flush=True)
