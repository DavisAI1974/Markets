"""S72 eyeball v2 — SMOOTHER individual curves, GROUPED by type (short/long x win/lose), mix of durations.
Per-trade display smoothing (60s), NOT averaged across trades. Flow + price both shown to see convergence."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,"/home/user/Markets"); sys.path.insert(0,"/home/user/Markets/research/shape_s71")
sys.path.insert(0,"/home/user/Markets/scripts")
import arc_gate as AG
from arc_gate import load_raw, build_channels, median_spread_bps, run_kraken_cell, KRAKEN
CPS=10; SMOOTH=20; DISP=60*CPS; THETA=20.0   # DISP = 60s display moving-average on top of the 20s flow
PRE=30*CPS; HZ=200*CPS
def mav(a,w):
    if w<=1: return a
    k=np.ones(w)/w; return np.convolve(a,k,mode="same")
def analyze(coin):
    path=f"/tmp/kbook/{coin}_book.jsonl"; cfg=[c for c in KRAKEN if c.coin==coin][0]
    raw=load_raw(path); ch,g=build_channels(path,cfg.K,20,raw=raw)
    mid=np.asarray(g["mid"],float); bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    hs=median_spread_bps(path,raw=raw)/2.0; N=len(mid)
    res,_=run_kraken_cell(cfg,mid,buy,sell,bb,ba,hs); flow=AG.rolling_imb(buy,sell,SMOOTH)
    legs=[]
    for l in res.legs:
        o=int(l.open_idx); c=int(l.close_idx); s=int(l.side)
        if o-PRE<0 or o+HZ>=N or c<=o: continue
        legs.append((o,c,s,float(l.net_bps),(c-o)*0.1))
    dur=np.array([x[4] for x in legs]); net=np.array([x[3] for x in legs]); dmed=np.median(dur)
    groups={"short-winner":[],"long-winner":[],"short-loser":[],"long-loser":[]}
    for x in legs:
        sh = x[4]<=dmed; wn = x[3]>0
        groups[("short" if sh else "long")+("-winner" if wn else "-loser")].append(x)
    return dict(mid=mid,flow=flow,groups=groups,coin=coin,dmed=dmed)
def price_turn(pf):
    rm=-1e9
    for i in range(len(pf)):
        rm=max(rm,pf[i])
        if pf[i]<rm-THETA: return i
    return None
def plot_coin(D,seed=1,ncol=5):
    coin=D["coin"]; mid=D["mid"]; flow=D["flow"]; rng=np.random.default_rng(seed)
    order=["short-winner","long-winner","short-loser","long-loser"]
    fig,axs=plt.subplots(4,ncol,figsize=(4.0*ncol,12)); tsec=(np.arange(PRE+HZ+1)-PRE)*0.1
    for r,typ in enumerate(order):
        pool=D["groups"][typ]
        pick=[pool[i] for i in rng.choice(len(pool),min(ncol,len(pool)),replace=False)] if pool else []
        for cix in range(ncol):
            ax=axs[r,cix]
            if cix>=len(pick):
                ax.axis("off"); continue
            o,c,s,net,dur=pick[cix]; lo=o-PRE; hi=o+HZ
            fl=mav(flow[lo:hi+1]*s, DISP)                       # 60s-smoothed exhaustion
            pf=mav(s*(mid[lo:hi+1]-mid[o])/mid[o]*1e4, 20*CPS)  # 20s-smoothed price move (bps)
            ax.plot(tsec,fl,color="C0",lw=1.5); ax.axhline(0,color="0.6",lw=0.5)
            ax.axvline(0,color="k",ls="--",lw=0.8,alpha=0.6)
            ax2=ax.twinx(); ax2.plot(tsec,pf,color="C3",lw=1.5)
            csec=(c-o)*0.1
            if csec<=200: ax.axvline(csec,color="green",ls=":",lw=1.3)
            ti=price_turn(pf[PRE:])
            if ti is not None: ax2.axvline(ti*0.1,color="red",lw=1.1,alpha=0.7)
            if cix==0: ax.set_ylabel(typ,fontsize=10,color="C0")
            ax.set_title(f"net{net:+.0f}bp dur{dur:.0f}s",fontsize=8)
            ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)
    fig.suptitle(f"{coin}_kraken — individual trades GROUPED by type (rows), 60s-smoothed  |  "
                 f"blue=exhaustion/flow (L)  red=price move bps (R)  black--=entry  green:=close  red|=price turn",fontsize=11)
    fig.tight_layout(rect=[0,0,1,0.97]); p=f"/tmp/kbook/{coin}_grouped.png"; fig.savefig(p,dpi=95); plt.close(); return p
if __name__=="__main__":
    import sys as _s
    coins=_s.argv[1:] or ["btc","eth","sol","xrp","doge"]
    for coin in coins:
        D=analyze(coin); p=plot_coin(D); print(f"{coin}: dmed={D['dmed']:.0f}s  ->  {p}",flush=True)
