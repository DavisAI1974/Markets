"""S74 FINAL A/B/C gate on the NATURAL-EXTENT (full-head, leakage-free) features + the fixed-window
cumulative feature. Decision per-trade; net/dur from the LIVE run_kraken_cell (cached). CAP=$5000."""
import numpy as np
CAP = 5000.0
COINS = ["btc", "eth", "sol", "xrp"]
NATF = ["extent","conv_n","area_n","t_infl","rise_last3","q25","q50","q75","below0","dip","peak"]

def metrics(fire, net, win, short, hours):
    g = net[fire].sum()
    sl=(~win)&short; ll=(~win)&~short
    return dict(winpct=(net[fire]>0).mean()*100 if fire.sum() else float("nan"),
                dph=g/1e4*CAP/hours, firedpct=fire.mean()*100,
                sl=int((~fire&sl).sum()), slt=int(sl.sum()),
                ll=int((~fire&ll).sum()), llt=int(ll.sum()),
                w=int((~fire&win).sum()), wt=int(win.sum()))

def energy_gate(peak, net, dur):
    win=net>0; med=np.median(dur); short=dur<med
    m=lambda k: float(peak[k].mean()) if k.sum() else 0.0
    a_sl=m((~win)&short); a_sw=m(win&short); a_ll=m((~win)&~short); a_lw=m(win&~short)
    d_lose=np.minimum(np.abs(peak-a_sl),np.abs(peak-a_ll))
    d_win =np.minimum(np.abs(peak-a_sw),np.abs(peak-a_lw))
    return ~(d_lose<d_win)

def eq_skip(v, win, direction, frac):
    n=len(v); k=int(frac*n); order=np.argsort(-v if direction>0 else v)
    fire=np.ones(n,bool); fire[order[:k]]=False; return fire

def main():
    d2 = {c: np.load(f"/tmp/kbook/{c}_feats2.npz") for c in COINS}   # fixed-window (has late_integral, net_area_ratio)
    for coin in COINS:
        nat=np.load(f"/tmp/kbook/{coin}_nat.npz")
        net=nat["net"]; dur=nat["dur"]; hours=float(nat["hours"]); win=net>0
        med=np.median(dur); short=dur<med
        F={k:nat[k] for k in NATF}
        # bring in fixed-window integrated-flow features (aligned differently: use natural's own area_n/below0/dip)
        print(f"\n############### {coin.upper()} n={len(net)} base win%={win.mean()*100:.1f} {hours:.1f}h ###############")
        ung=metrics(np.ones(len(net),bool),net,win,short,hours)
        print(f"  UNGATED win%={win.mean()*100:.1f} $/hr={ung['dph']:.3f}")
        # (A) energy
        fireA=energy_gate(F["peak"],net,dur); mA=metrics(fireA,net,win,short,hours)
        print(f"  (A) ENERGY : win%={mA['winpct']:.1f} $/hr={mA['dph']:.3f} fired={mA['firedpct']:.0f}% "
              f"SL={mA['sl']}/{mA['slt']} LL={mA['ll']}/{mA['llt']} WINskip={mA['w']}/{mA['wt']}")
        # (B) best single natural-extent EQUATION feature (exclude raw energy 'peak')
        res=[]
        for k in NATF:
            if k=="peak": continue
            v=F[k]; gap=v[~win].mean()-v[win].mean(); dr=1 if gap>0 else -1
            for fr in (0.05,0.10,0.15,0.20,0.30):
                mm=metrics(eq_skip(v,win,dr,fr),net,win,short,hours)
                res.append((mm['dph'],k,dr,fr,mm))
        res.sort(reverse=True)
        print(f"  (B) EQUATION top-3 (natural-extent shape):")
        for dph,k,dr,fr,mm in res[:3]:
            print(f"      {k:11} skip {fr*100:2.0f}% {'hi' if dr>0 else 'lo'}-tail: win%={mm['winpct']:.1f} $/hr={dph:.3f} "
                  f"fired={mm['firedpct']:.0f}% SL={mm['sl']}/{mm['slt']} LL={mm['ll']}/{mm['llt']} WINskip={mm['w']}/{mm['wt']}")
        # also the fixed-window integrated-flow gate (late_integral / net_area_ratio) for the same coin
        fx=d2[coin]; netx=fx["net"]; durx=fx["dur"]; winx=netx>0; shx=durx<np.median(durx); hx=float(fx["hours"])
        for feat in ("late_integral","net_area_ratio"):
            v=fx[feat]; dr=1 if v[~winx].mean()>v[winx].mean() else -1
            best=max(((metrics(eq_skip(v,winx,dr,fr),netx,winx,shx,hx)['dph'],fr) for fr in (0.05,0.1,0.15,0.2)),)
            dph,fr=best; mm=metrics(eq_skip(v,winx,dr,fr),netx,winx,shx,hx)
            print(f"      [fixed-win] {feat:14} skip {fr*100:2.0f}% {'lo' if dr<0 else 'hi'}-tail: "
                  f"win%={mm['winpct']:.1f} $/hr={dph:.3f} SL={mm['sl']}/{mm['slt']} LL={mm['ll']}/{mm['llt']} WINskip={mm['w']}/{mm['wt']}")
        # (C) stack: energy-skip AND equation-confirms-loser (best B feature)
        bk,bdr=res[0][1],res[0][2]; v=F[bk]
        thr=np.quantile(v,0.60 if bdr>0 else 0.40)
        eqloser=(v>=thr) if bdr>0 else (v<=thr)
        fireC=~((~fireA)&eqloser); mC=metrics(fireC,net,win,short,hours)
        print(f"  (C) STACK energy AND {bk}: win%={mC['winpct']:.1f} $/hr={mC['dph']:.3f} fired={mC['firedpct']:.0f}% "
              f"SL={mC['sl']}/{mC['slt']} LL={mC['ll']}/{mC['llt']} WINskip={mC['w']}/{mC['wt']}")
    print("\nDONE")

if __name__=="__main__":
    main()
