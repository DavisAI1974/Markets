"""S71 SHAPE dive: does the PRE-ONSET ignition arc SHAPE predict a PROFITABLE ride?
Outcomes/fills from the LIVE executor (run_kraken_cell) untouched. Pre-onset limb ONLY for
predictive features (leakage-free). Per-cell separation (AUC, walk-forward OOS, shift-null) +
the arc-shape profit GATE (gated vs un-gated net bps/hr). Additive; commits nothing."""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = "/home/user/Markets"
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)
from _birth_probe import _depthK
from _liquidity_dive import build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN
OUT = "/tmp/claude-0/-home-user-Markets/9c530e49-5a24-51c2-b8c4-60c751ae23a0/scratchpad"
CPS = 10                                   # cells per second (0.1s book)
PRE_SEC, POST_SEC, SMOOTH_SEC = 45, 25, 20
PRE, POST = PRE_SEC*CPS, POST_SEC*CPS

def load_raw(path):
    ts, mid, buy, sell, spread = [], [], [], [], []
    b1,b3,b5,b10,a1,a3,a5,a10 = [],[],[],[],[],[],[],[]
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            ts.append(r["ts"]); mid.append(r["mid"]); spread.append(r.get("spread"))
            buy.append(r.get("buy",0.0) or 0.0); sell.append(r.get("sell",0.0) or 0.0)
            x=_depthK(r["bids"]); b1.append(x[0]);b3.append(x[1]);b5.append(x[2]);b10.append(x[3])
            y=_depthK(r["asks"]); a1.append(y[0]);a3.append(y[1]);a5.append(y[2]);a10.append(y[3])
    return dict(ts=np.array(ts), mid=np.array(mid), buy=np.array(buy), sell=np.array(sell),
                spread=np.array([np.nan if v is None else v for v in spread],float),
                bidK={1:np.array(b1),3:np.array(b3),5:np.array(b5),10:np.array(b10)},
                askK={1:np.array(a1),3:np.array(a3),5:np.array(a5),10:np.array(a10)})

def rolling_imb(buy, sell, w_sec):
    w=int(w_sec*CPS); cb=np.concatenate([[0.],np.cumsum(buy)]); cs=np.concatenate([[0.],np.cumsum(sell)])
    ix=np.arange(len(buy)); lo=np.maximum(ix+1-w,0)
    B=cb[ix+1]-cb[lo]; S=cs[ix+1]-cs[lo]; tot=B+S
    out=np.zeros(len(buy)); nz=tot>0; out[nz]=(B[nz]-S[nz])/tot[nz]
    return out

def preonset_features(f):
    """f = signed with-trade flow over the FULL window; use ONLY [0:PRE+1] (strictly pre-onset)."""
    pre = f[:PRE+1]
    x = (np.arange(PRE+1)-PRE)*0.1              # seconds -45..0
    # level-invariant-ish shape descriptors of the IGNITION limb
    sl = np.polyfit(x, pre, 1)[0]               # rise slope (flow/s)
    ac = np.polyfit(x, pre, 2)[0]               # curvature / acceleration
    rng = pre.max()-pre.min()+1e-9
    prn = (pre-pre.min())/rng                   # normalized shape [0,1]
    sl_n = np.polyfit(x, prn, 1)[0]             # normalized rise slope (level-invariant)
    ac_n = np.polyfit(x, prn, 2)[0]             # normalized curvature (level-invariant)
    end = pre[-1]                               # flow at onset- (last readable)
    rise = pre[-1]-pre.min()                    # net rise into the turn
    peak_t = (int(np.argmax(pre))-PRE)*0.1      # peak timing rel onset (<=0)
    area = pre.mean()                           # area under limb (signed)
    late = np.polyfit(x[-10*CPS:], pre[-10*CPS:], 1)[0]  # last-10s slope (accelerating in?)
    mono = float(np.mean(np.diff(pre) > 0))     # rising fraction
    return [sl, ac, sl_n, ac_n, end, rise, peak_t, area, late, mono]
FEATNAMES = ["slope","accel","slope_n","accel_n","end_lvl","rise","peak_t","area","late_slope","mono","fs_strength"]

def false_start(pre):
    """Detect Greg's 'failed-first-attempt / spring / shakeout': in the pre-onset signed-flow limb,
    an early BUMP (tries to lift), a PULLBACK toward baseline (absorption/rejection), then the real
    LAUNCH into onset. Strictly pre-onset (leakage-free). Level-invariant (normalized to own range).
    Returns (present:0/1, bump_mag, retrace_frac, launch_rate, strength)."""
    amp = pre[-1] - pre.min()
    if amp < 0.05:                                    # no real launch into the turn
        return 0, 0.0, 0.0, 0.0, 0.0, -1
    z = (pre - pre.min()) / (amp + 1e-9)              # [0,1]; onset ~ top on a launch
    if z[-1] < 0.6:                                   # onset must end high (a launch, not a fade)
        return 0, 0.0, 0.0, 0.0, 0.0, -1
    n = len(z)
    # local extrema (plateau-tolerant): strictly-greater / strictly-less than neighbors
    ismax = np.r_[False, (z[1:-1] > z[:-2]) & (z[1:-1] >= z[2:]), False]
    ismin = np.r_[False, (z[1:-1] < z[:-2]) & (z[1:-1] <= z[2:]), False]
    maxi = np.where(ismax)[0]; mini = np.where(ismin)[0]
    best = (0.0, 0.0, 0.0, 0.0, -1)
    for b in maxi:                                    # bump candidate
        if b >= n - 3:            # bump must precede a launch tail
            continue
        hb = z[b]
        if hb < 0.15:             # bump must actually try to lift
            continue
        dips = mini[(mini > b)]
        if len(dips) == 0:
            continue
        d = dips[np.argmin(z[dips])]                  # deepest dip after the bump
        hd = z[d]
        retr = (hb - hd) / (hb + 1e-9)                # fraction retraced back toward baseline
        if retr < 0.30:           # need a real pushback
            continue
        # a real launch AFTER the dip that exceeds the bump and reaches onset high
        tail = z[d:]
        if tail.max() <= hb + 0.05:
            continue
        xr = (np.arange(len(tail)))*0.1
        lr = np.polyfit(xr, tail, 1)[0] if len(tail) > 2 else 0.0   # launch rise-rate
        strength = hb * retr * max(lr, 0.0)
        if strength > best[3]:
            best = (hb, retr, lr, strength, d)
    hb, retr, lr, st, d = best
    present = int(st > 0)
    return present, hb, retr, lr, st, d

def auc(y, s):
    y=np.asarray(y); s=np.asarray(s); p=s[y==1]; n=s[y==0]
    if len(p)==0 or len(n)==0: return np.nan
    r=np.argsort(np.argsort(np.concatenate([p,n])))
    return (r[:len(p)].sum()-len(p)*(len(p)-1)/2)/(len(p)*len(n))

def process_coin(coin):
    path=f"/tmp/kbook/{coin}_book.jsonl"
    cfg=[c for c in KRAKEN if c.coin==coin][0]
    raw=load_raw(path)
    ch,g=build_channels(path,cfg.K,20,raw=raw)
    mid=np.asarray(g["mid"],float); bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    hs=median_spread_bps(path,raw=raw)/2.0
    N=len(mid); hours=N*0.1/3600.0
    res,_=run_kraken_cell(cfg,mid,buy,sell,bb,ba,hs)
    imb=rolling_imb(buy,sell,SMOOTH_SEC)
    X,net,gross,arcs,fs=[],[],[],[],[]
    for l in res.legs:
        o=int(l.open_idx); c=int(l.close_idx); lo=o-PRE; hi=o+POST
        if lo<0 or hi>=N or c<=o: continue
        f=imb[lo:hi+1]*int(l.side)
        pre=f[:PRE+1]
        fsr=false_start(pre)                             # (present,bump,retrace,launch_rate,strength,dip_idx)
        X.append(preonset_features(f)+[fsr[4]])          # append false-start STRENGTH as a feature
        fs.append(fsr); net.append(float(l.net_bps)); gross.append(float(l.gross_bps)); arcs.append(f.copy())
    return dict(coin=coin, X=np.array(X), net=np.array(net), gross=np.array(gross),
                fs=np.array(fs), arcs=np.array(arcs), hours=hours, n_all=len(res.legs))

def analyze(d):
    coin=d["coin"]; X=d["X"]; net=d["net"]; gross=d["gross"]; hours=d["hours"]; fs=d["fs"]
    n=len(net); fpres=fs[:,0].astype(int); fstr=fs[:,4]
    # LABELS: profitable in executor's deployed frame (net>0), and clears 10bp taker round-trip
    y_mk=(net>0).astype(int); y_tk=(gross>10).astype(int)
    base_mk=y_mk.mean(); base_tk=y_tk.mean()
    print(f"\n===== {coin}_kraken =====", flush=True)
    print(f"  legs={n}  hours={hours:.1f}  base win-rate: maker(net>0)={base_mk:.3f}  taker(gross>10bp)={base_tk:.3f}", flush=True)
    print(f"  UNGATED total net_bps={net.sum():.0f}  mean/leg={net.mean():.3f}  net bps/hr={net.sum()/hours:.1f}", flush=True)
    # univariate in-sample AUC vs maker label
    print("  univariate pre-onset feature AUC (net>0):", flush=True)
    for j,nm in enumerate(FEATNAMES):
        print(f"    {nm:11s} {auc(y_mk, X[:,j]):.3f}", flush=True)
    # walk-forward: tune first 60%, score last 40% (time-ordered legs)
    cut=int(n*0.6)
    tr=slice(0,cut); te=slice(cut,n)
    out={}
    for lbl,y in [("maker",y_mk),("taker",y_tk)]:
        ytr=y[tr]
        if ytr.sum()==0 or ytr.sum()==len(ytr):
            out[lbl]=None; continue
        sc=StandardScaler().fit(X[tr])
        clf=LogisticRegression(max_iter=1000,C=1.0).fit(sc.transform(X[tr]),ytr)
        p_is=clf.predict_proba(sc.transform(X[tr]))[:,1]
        p_oos=clf.predict_proba(sc.transform(X[te]))[:,1]
        auc_is=auc(y[tr],p_is); auc_oos=auc(y[te],p_oos)
        # shift-null: shuffle train labels, refit, OOS AUC (200x)
        rng=np.random.default_rng(0); nulls=[]
        for _ in range(200):
            yp=rng.permutation(ytr)
            if yp.sum()==0 or yp.sum()==len(yp): continue
            cn=LogisticRegression(max_iter=200,C=1.0).fit(sc.transform(X[tr]),yp)
            nulls.append(auc(y[te],cn.predict_proba(sc.transform(X[te]))[:,1]))
        nulls=np.array(nulls); z=(auc_oos-nulls.mean())/(nulls.std()+1e-9)
        # top vs bottom OOS-quartile win-rate lift
        q=np.quantile(p_oos,[0.25,0.75]); yte=y[te]
        top=yte[p_oos>=q[1]].mean() if (p_oos>=q[1]).any() else np.nan
        bot=yte[p_oos<=q[0]].mean() if (p_oos<=q[0]).any() else np.nan
        out[lbl]=dict(auc_is=auc_is,auc_oos=auc_oos,z=z,null=nulls.mean(),top=top,bot=bot,
                      clf=clf,sc=sc,p_oos=p_oos)
        print(f"  [{lbl}] AUC in-samp={auc_is:.3f}  OOS={auc_oos:.3f}  shift-null={nulls.mean():.3f} (z={z:+.1f})  "
              f"OOS win-rate topQ={top:.3f} botQ={bot:.3f}", flush=True)
    # ---- FALSE-START ('spring/shakeout') group test: winners vs losers, present vs absent ----
    freq=fpres.mean()
    print(f"  false-start present in {fpres.sum()}/{n} legs ({freq*100:.1f}%)", flush=True)
    if fpres.sum()>=8 and (1-fpres).sum()>=8:
        wp=y_mk[fpres==1].mean(); wa=y_mk[fpres==0].mean()
        npn=net[fpres==1].mean(); nan_=net[fpres==0].mean()
        print(f"    win-rate(net>0): false-start={wp:.3f}  clean-launch={wa:.3f}  (lift {wp-wa:+.3f})", flush=True)
        print(f"    mean net_bps:    false-start={npn:+.2f}  clean-launch={nan_:+.2f}", flush=True)
        print(f"    univariate AUC: fs_strength={auc(y_mk,fstr):.3f}  vs best smooth "
              f"{max((abs(auc(y_mk,X[:,j])-0.5) for j in range(len(FEATNAMES)-1)))+0.5:.3f}", flush=True)
        # walk-forward OOS group
        wp_o=y_mk[te][fpres[te]==1]; wa_o=y_mk[te][fpres[te]==0]
        if len(wp_o)>=4 and len(wa_o)>=4:
            print(f"    OOS win-rate: false-start={wp_o.mean():.3f} (n={len(wp_o)})  "
                  f"clean={wa_o.mean():.3f} (n={len(wa_o)})", flush=True)
    # ---- MONEY: arc-shape GATE on OOS (last 40%) ----
    net_te=net[te]; hrs_te=hours*(n-cut)/n
    ung=net_te.sum()
    print(f"  --- OOS money (last 40%, {len(net_te)} legs, {hrs_te:.1f}h) ---", flush=True)
    print(f"    UNGATED: net_bps={ung:.0f}  bps/hr={ung/hrs_te:.1f}  legs={len(net_te)}", flush=True)
    if out.get("maker"):
        p=out["maker"]["p_oos"]
        for thr in (0.5,0.55,0.6):
            keep=p>=thr; g=net_te[keep].sum()
            print(f"    GATE logistic p>={thr}: net_bps={g:.0f}  bps/hr={g/hrs_te:.1f}  legs={keep.sum()} "
                  f"({keep.mean()*100:.0f}% kept)  PnL retained={100*g/ung if ung!=0 else float('nan'):.0f}%", flush=True)
    # false-start gate variant
    keep=fpres[te]==1; g=net_te[keep].sum()
    if keep.sum()>0:
        print(f"    GATE false-start-present: net_bps={g:.0f}  bps/hr={g/hrs_te:.1f}  legs={keep.sum()} "
              f"({keep.mean()*100:.0f}% kept)  PnL retained={100*g/ung if ung!=0 else float('nan'):.0f}%", flush=True)
    return dict(coin=coin, d=d, y_mk=y_mk, X=X, net=net, out=out, tr=tr, te=te, fpres=fpres)

if __name__=="__main__":
    coins=["btc","eth","sol","xrp","doge"]
    results={}
    for c in coins:
        print(f"\n... loading+running {c} (live executor) ...", flush=True)
        try:
            d=process_coin(c); results[c]=analyze(d)
        except Exception as e:
            print(f"  {c} FAILED: {e}", flush=True)
    # winners vs losers mean pre-onset arc overlay (per coin that separated)
    tsec=(np.arange(PRE+POST+1)-PRE)*0.1
    fig,axs=plt.subplots(len(results),1,figsize=(10,3.2*len(results)),squeeze=False)
    for i,(c,R) in enumerate(results.items()):
        arcs=R["d"]["arcs"]; y=R["y_mk"]; ax=axs[i,0]
        win=arcs[y==1].mean(0); los=arcs[y==0].mean(0)
        ax.plot(tsec,win,color="C2",lw=2,label=f"profitable (net>0, n={int(y.sum())})")
        ax.plot(tsec,los,color="C3",lw=2,label=f"sub-fee/loser (n={int((1-y).sum())})")
        ax.axvline(0,color="k",ls="--",lw=1,alpha=0.6); ax.axhline(0,color="gray",lw=0.6)
        ax.axvspan(-PRE_SEC,0,color="k",alpha=0.04)
        o=R["out"].get("maker"); tag=f"OOS AUC {o['auc_oos']:.2f} (z{o['z']:+.0f})" if o else "n/a"
        ax.set_title(f"{c}_kraken — mean with-trade FLOW arc, winners vs losers  [{tag}]  (shaded = pre-onset, the only readable-live limb)")
        ax.set_ylabel("mean flow"); ax.legend(fontsize=7,loc="upper left"); ax.grid(alpha=0.25)
    axs[-1,0].set_xlabel("seconds relative to onset (t=0)")
    plt.tight_layout(); pp=os.path.join(OUT,"kraken_winner_loser_arcs.png")
    plt.savefig(pp,dpi=110); plt.close()
    print(f"\nsaved {pp}", flush=True)

    # ---- FALSE-START vs CLEAN-LAUNCH mean pre-onset arc (btc) + self-alignment smear check ----
    if "btc" in results:
        R=results["btc"]; arcs=R["d"]["arcs"]; fs=R["d"]["fs"]
        fp=fs[:,0].astype(int); dipi=fs[:,5].astype(int)
        pre_x=(np.arange(PRE+1)-PRE)*0.1
        fig2,(a1,a2)=plt.subplots(2,1,figsize=(10,7))
        # panel1: onset-aligned mean pre-onset arc, false-start vs clean-launch
        fsl=arcs[fp==1][:,:PRE+1]; cll=arcs[fp==0][:,:PRE+1]
        a1.plot(pre_x,fsl.mean(0),color="C0",lw=2,label=f"false-start-then-launch (n={len(fsl)})")
        a1.plot(pre_x,cll.mean(0),color="C1",lw=2,label=f"clean single-shot launch (n={len(cll)})")
        a1.axvline(0,color="k",ls="--",lw=1,alpha=0.6); a1.axhline(0,color="gray",lw=0.6)
        a1.set_title("btc_kraken — mean PRE-ONSET signed-flow limb: false-start vs clean-launch (ONSET-aligned)")
        a1.set_ylabel("mean flow"); a1.legend(fontsize=8); a1.grid(alpha=0.25)
        # panel2: SELF-aligned on the pushback (dip) time — does the bump-pullback sharpen?
        W=150  # +-15s around the dip
        seg=[]
        for k in np.where(fp==1)[0]:
            di=dipi[k]
            if di<W or di>PRE-W: continue
            seg.append(arcs[k][di-W:di+W+1])
        if seg:
            seg=np.array(seg); sx=(np.arange(2*W+1)-W)*0.1
            a2.plot(sx,seg.mean(0),color="C0",lw=2,label=f"false-start legs, aligned on OWN pushback (n={len(seg)})")
        # same legs onset-aligned, cropped to same width for contrast
        a2.axvline(0,color="k",ls="--",lw=1,alpha=0.6); a2.axhline(0,color="gray",lw=0.6)
        a2.set_title("SELF-ALIGNED on pushback time (t=0 = the dip) — bump-pullback-relaunch morphology")
        a2.set_xlabel("seconds relative to pushback"); a2.set_ylabel("mean flow")
        a2.legend(fontsize=8); a2.grid(alpha=0.25)
        plt.tight_layout(); pp2=os.path.join(OUT,"btc_false_start_arcs.png")
        plt.savefig(pp2,dpi=110); plt.close()
        print(f"saved {pp2}", flush=True)
    print("DONE", flush=True)
